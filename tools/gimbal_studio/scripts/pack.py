"""Build one-folder app with PyInstaller."""

import subprocess
import sys
from pathlib import Path


def build_pyinstaller_command(python: str, root: Path) -> list[str]:
    return [
        python,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--name",
        "GimbalStudio",
        "--paths",
        str(root / "src"),
        "--collect-data",
        "gimbal_studio",
        str(root / "src" / "gimbal_studio" / "__main__.py"),
    ]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    subprocess.check_call(build_pyinstaller_command(sys.executable, root))


if __name__ == "__main__":
    main()
