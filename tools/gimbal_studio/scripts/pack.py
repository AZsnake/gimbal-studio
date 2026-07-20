"""Build one-folder app with PyInstaller."""

import subprocess
import sys
from pathlib import Path


root = Path(__file__).resolve().parents[1]
subprocess.check_call(
    [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--name",
        "GimbalStudio",
        "--paths",
        str(root / "src"),
        str(root / "src" / "gimbal_studio" / "__main__.py"),
    ]
)
