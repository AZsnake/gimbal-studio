from pathlib import Path

from gimbal_studio.project.ini_io import group_command, load_ini, save_ini
from gimbal_studio.project.models import ActionGroup, enabled_steers


FIXTURE = Path(__file__).parent / "fixtures" / "minimal_bes.ini"


def test_load_enabled_and_groups():
    project = load_ini(FIXTURE)

    enabled = enabled_steers(project)
    assert [steer.title for steer in enabled] == ["水平", "倾斜"]
    assert enabled[0].id == 0
    assert enabled[0].pmin == 500
    assert len(project.groups) == 2
    assert project.groups[0].moves[0] == (0, 1500, 1000)
    assert project.meta["zide_version"] == "Zide V5.99"


def test_roundtrip_preserves_unknown_section(tmp_path):
    project = load_ini(FIXTURE)
    out = tmp_path / "out.ini"

    save_ini(project, out)

    text = out.read_text(encoding="utf-8")
    assert "[LD0]" in text
    assert "ldName=未命名" in text
    assert "#031P0000T0000!" in text

    reloaded = load_ini(out)
    assert enabled_steers(reloaded)[0].title == "水平"
    assert reloaded.groups[1].moves[0] == (0, 1100, 1800)


def test_save_syncs_group_header_with_slot_count(tmp_path):
    project = load_ini(FIXTURE)
    assert "S31" not in project.meta["_group_header"]

    out = tmp_path / "out.ini"
    save_ini(project, out)

    text = out.read_text(encoding="utf-8")
    assert "------S31------" in text
    assert "#031P0000T0000!" in text


def test_group_command_builds_multi_servo_command():
    group = ActionGroup(index=3, moves=[(0, 1100, 1800), (1, 1500, 1800)])

    cmd = group_command(group)
    assert cmd.startswith("{G0003#000P1100T1800!#001P1500T1800!")
    assert cmd.endswith("}")
    assert "#031P0000T0000!" in cmd


def test_group_command_compact_omits_unused_slots():
    """Online/HID must fit one report: live multi (no G tag), no #031 padding."""
    group = ActionGroup(index=3, moves=[(0, 1100, 1800), (1, 1500, 1800)])

    cmd = group_command(group, compact=True)
    assert cmd == "{#000P1100T1800!#001P1500T1800!}"
    assert "#031P0000T0000!" not in cmd
    assert not cmd.startswith("{G")
    assert len(cmd.encode("ascii")) <= 62


def test_group_command_compact_strips_ini_zero_padding():
    """Loaded Zide groups keep 32 slots; online must drop P0000T0000 fillers."""
    moves = [(0, 1500, 1000), (1, 1100, 1800)] + [
        (slot, 0, 0) for slot in range(2, 32)
    ]
    group = ActionGroup(index=0, moves=moves)

    cmd = group_command(group, compact=True)
    assert cmd == "{#000P1500T1000!#001P1100T1800!}"
    assert "#002P0000T0000!" not in cmd
    assert len(cmd.encode("ascii")) <= 62


def test_load_real_bes_if_present():
    candidates = list(
        Path(__file__).resolve().parents[3].joinpath("docs").rglob("config_bes.ini")
    )
    if not candidates:
        return

    project = load_ini(candidates[0])

    assert len(enabled_steers(project)) >= 2
    assert len(project.groups) >= 1
