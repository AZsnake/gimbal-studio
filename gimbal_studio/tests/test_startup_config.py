from pathlib import Path

from gimbal_studio.project.defaults import default_project, ensure_default_config
from gimbal_studio.project.ini_io import group_command, load_ini
from gimbal_studio.project.models import enabled_steers
from gimbal_studio.project.startup import resolve_startup_path


def test_default_project_is_two_axis_showcase() -> None:
    project = default_project()
    steers = enabled_steers(project)
    assert len(steers) == 2
    assert [s.id for s in steers] == [0, 1]
    assert [s.title for s in steers] == ["水平", "倾斜"]
    assert len(project.groups) >= 20
    assert [g.index for g in project.groups] == list(range(len(project.groups)))
    pans = [pwm for group in project.groups for sid, pwm, _ in group.moves if sid == 0]
    tilts = [pwm for group in project.groups for sid, pwm, _ in group.moves if sid == 1]
    assert min(pans) <= 700 and max(pans) >= 2300
    assert min(tilts) <= 800 and max(tilts) >= 2200
    assert max(t for g in project.groups for *_, t in g.moves) <= 450
    # Compact online frames stay small (no 32-slot padding noise).
    for group in project.groups:
        cmd = group_command(group, compact=True)
        assert "#031" not in cmd
        assert len(cmd.encode("ascii")) <= 62

def test_ensure_default_config_writes_loadable_ini(tmp_path: Path) -> None:
    path = tmp_path / "config.ini"
    assert not path.exists()
    ensure_default_config(path)
    assert path.is_file()
    loaded = load_ini(path)
    assert len(enabled_steers(loaded)) == 2
    assert len(loaded.groups) >= 20


def test_resolve_prefers_valid_last_path(tmp_path: Path) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / "config.ini").write_text("[global]\nx=1\n", encoding="utf-8")
    last = tmp_path / "last.ini"
    last.write_text("[global]\ny=2\n", encoding="utf-8")

    assert resolve_startup_path(cwd, str(last)) == last.resolve()


def test_resolve_falls_back_to_cwd_config(tmp_path: Path) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    local = cwd / "config.ini"
    local.write_text("[global]\nx=1\n", encoding="utf-8")

    assert resolve_startup_path(cwd, str(tmp_path / "missing.ini")) == local.resolve()
    assert resolve_startup_path(cwd, "") == local.resolve()
    assert resolve_startup_path(cwd, None) == local.resolve()


def test_resolve_creates_default_when_nothing_exists(tmp_path: Path) -> None:
    cwd = tmp_path / "empty"
    cwd.mkdir()
    path = resolve_startup_path(cwd, None)
    assert path == (cwd / "config.ini").resolve()
    assert path.is_file()
    assert len(load_ini(path).groups) >= 20
