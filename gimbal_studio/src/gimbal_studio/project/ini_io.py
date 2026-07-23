import re
from pathlib import Path

from gimbal_studio.project.models import ActionGroup, Project, SteerChannel
from gimbal_studio.protocol import build_multi, format_group_line, parse_group_body


_GROUP_KEY_RE = re.compile(r"G(\d+)$", re.IGNORECASE)
_STEER_SECTION_RE = re.compile(r"steer(\d+)$", re.IGNORECASE)
_AUX_META_SECTIONS = ("cellName", "cellCount")
_AUX_META_NAMES = {name.lower(): name for name in _AUX_META_SECTIONS}
_INTERNAL_META_KEYS = {"_group_header", *("_" + name for name in _AUX_META_SECTIONS)}


def _parse_sections(text: str) -> dict[str, list[tuple[str, str]]]:
    sections: dict[str, list[tuple[str, str]]] = {}
    current: list[tuple[str, str]] | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith((";", "#")):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            current = sections.setdefault(name, [])
            continue
        if current is not None and "=" in raw_line:
            key, value = raw_line.split("=", 1)
            current.append((key.strip(), value.strip()))

    return sections


def _as_int(values: dict[str, str], key: str, default: int) -> int:
    try:
        return int(values.get(key, default))
    except (TypeError, ValueError):
        return default


def _parse_steer(items: list[tuple[str, str]], section_index: int) -> SteerChannel:
    values = {key.lower(): value for key, value in items}
    return SteerChannel(
        title=values.get("title", ""),
        id=_as_int(values, "id", section_index),
        bias=_as_int(values, "bias", 0),
        pmin=_as_int(values, "pmin", 500),
        pmax=_as_int(values, "pmax", 2500),
        lab_left=values.get("lableft", ""),
        lab_right=values.get("labright", ""),
        enable=values.get("enable", "false").lower() == "true",
        x=_as_int(values, "x", 0),
        y=_as_int(values, "y", 0),
    )


def load_ini(path: Path) -> Project:
    sections = _parse_sections(path.read_text(encoding="utf-8-sig"))
    project = Project()

    for section, items in sections.items():
        section_lower = section.lower()
        if section_lower == "global":
            project.meta.update(items)
            continue
        if section_lower == "group":
            for key, value in items:
                match = _GROUP_KEY_RE.fullmatch(key)
                if match:
                    project.groups.append(
                        ActionGroup(int(match.group(1)), parse_group_body(value))
                    )
                elif key.upper() == "GROUP":
                    project.meta["_group_header"] = value
            continue

        steer_match = _STEER_SECTION_RE.fullmatch(section)
        if steer_match:
            project.steers.append(_parse_steer(items, int(steer_match.group(1))))
        elif section_lower in _AUX_META_NAMES:
            project.meta[f"_{_AUX_META_NAMES[section_lower]}"] = items
        else:
            project.raw_sections[section] = items

    return project


def _append_section(
    lines: list[str], name: str, items: list[tuple[str, object]]
) -> None:
    if lines:
        lines.append("")
    lines.append(f"[{name}]")
    lines.extend(f"{key}={value}" for key, value in items)


def _group_header(total_slots: int) -> str:
    columns = "".join(f"------S{slot:02d}------" for slot in range(total_slots))
    return f"{{ NUM {columns}}}"


def _header_slot_count(header: str) -> int:
    return len(re.findall(r"S\d{2}", header))


def _resolve_group_header(project: Project, total_slots: int) -> str:
    loaded = project.meta.get("_group_header")
    if loaded is not None and _header_slot_count(loaded) == total_slots:
        return loaded
    return _group_header(total_slots)


def _total_slots(project: Project) -> int:
    ids = [steer.id for steer in project.steers if steer.enable]
    ids.extend(servo_id for group in project.groups for servo_id, _, _ in group.moves)
    return max(32, max(ids, default=-1) + 1)


def save_ini(project: Project, path: Path) -> None:
    lines: list[str] = []
    global_items = [
        (key, value)
        for key, value in project.meta.items()
        if key not in _INTERNAL_META_KEYS and not key.startswith("_")
    ]
    _append_section(lines, "global", global_items)

    total_slots = _total_slots(project)
    group_items: list[tuple[str, object]] = [
        ("GROUP", _resolve_group_header(project, total_slots))
    ]
    for group in sorted(project.groups, key=lambda item: item.index):
        line = format_group_line(group.index, group.moves, total_slots)
        key, value = line.split("=", 1)
        group_items.append((key, value))
    _append_section(lines, "group", group_items)

    for steer in project.steers:
        _append_section(
            lines,
            f"steer{steer.id}",
            [
                ("title", steer.title),
                ("id", steer.id),
                ("x", steer.x),
                ("y", steer.y),
                ("bias", steer.bias),
                ("pmin", steer.pmin),
                ("pmax", steer.pmax),
                ("labLeft", steer.lab_left),
                ("labRight", steer.lab_right),
                ("enable", str(steer.enable).lower()),
            ],
        )

    for name in _AUX_META_SECTIONS:
        items = project.meta.get(f"_{name}")
        if items is not None:
            _append_section(lines, name, items)

    for section, items in project.raw_sections.items():
        _append_section(lines, section, items)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _active_moves(
    moves: list[tuple[int, int, int]],
) -> list[tuple[int, int, int]]:
    """Drop Zide download padding slots (``#nnnP0000T0000!``)."""
    return [(servo_id, pwm, time_ms) for servo_id, pwm, time_ms in moves if not (pwm == 0 and time_ms == 0)]


def group_command(group: ActionGroup, *, compact: bool = False) -> str:
    """Build wire body for a group.

    - ``compact=True``: live execute like the control pad — ``build_multi`` of
      active servos only (no ``G`` tag, no ``P0000T0000`` padding). Fits one HID report.
    - ``compact=False``: pad to 32 slots (Zide download / .ini storage format).
    """
    if compact:
        return build_multi(_active_moves(group.moves))
    # format_group_line -> G0000={G0000#000P...!}; send the `{...}` value only.
    line = format_group_line(group.index, group.moves, total_slots=32)
    return line.split("=", 1)[1]
