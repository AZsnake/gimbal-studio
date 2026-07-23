import importlib.util
from pathlib import Path


def _load_pack_module():
    pack_py = Path(__file__).resolve().parents[1] / "scripts" / "pack.py"
    spec = importlib.util.spec_from_file_location("pack", pack_py)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pack_pyinstaller_collects_gimbal_studio_data():
    pack = _load_pack_module()
    root = Path(__file__).resolve().parents[1]
    command = pack.build_pyinstaller_command("python", root)

    collect_index = command.index("--collect-data")
    assert command[collect_index + 1] == "gimbal_studio"
    assert "--clean" in command
    hid_index = command.index("--hidden-import")
    assert command[hid_index + 1] == "hid"
