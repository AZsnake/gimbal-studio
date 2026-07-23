import re

from gimbal_studio.protocol.commands import build_move

_MOVE_RE = re.compile(r"#(\d{3})P(\d{4})T(\d{4})!")


def parse_group_body(body: str) -> list[tuple[int, int, int]]:
    return [(int(a), int(b), int(c)) for a, b, c in _MOVE_RE.findall(body)]


def format_group_line(index: int, moves: list[tuple[int, int, int]], total_slots: int = 32) -> str:
    by_id = {i: (p, t) for i, p, t in moves}
    parts = []
    for slot in range(total_slots):
        p, t = by_id.get(slot, (0, 0))
        parts.append(build_move(slot, p, t))
    tag = f"G{index:04d}"
    inner = tag + "".join(parts)
    return f"{tag}={{{inner}}}"
