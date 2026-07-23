"""Build one-folder app with PyInstaller."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def build_pyinstaller_command(python: str, root: Path) -> list[str]:
    command = [
        python,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "GimbalStudio",
        "--paths",
        str(root / "src"),
        "--collect-data",
        "gimbal_studio",
        "--hidden-import",
        "hid",
    ]
    # Linux desktop builds need Qt plugins and shiboken shared libs.
    # Avoid --collect-all PySide6: it pulls WebEngine/Qt3D and balloons the bundle.
    if sys.platform.startswith("linux"):
        command.extend(
            [
                "--collect-binaries",
                "PySide6",
                "--collect-data",
                "PySide6",
                "--collect-binaries",
                "shiboken6",
                "--exclude-module",
                "PySide6.QtWebEngine",
                "--exclude-module",
                "PySide6.QtWebEngineCore",
                "--exclude-module",
                "PySide6.QtWebEngineWidgets",
                "--exclude-module",
                "PySide6.QtWebEngineQuick",
                "--exclude-module",
                "PySide6.Qt3DCore",
                "--exclude-module",
                "PySide6.Qt3DRender",
                "--exclude-module",
                "PySide6.QtQuick3D",
                "--exclude-module",
                "PySide6.QtPdf",
                "--exclude-module",
                "PySide6.QtPdfWidgets",
            ]
        )
    command.append(str(root / "src" / "gimbal_studio" / "__main__.py"))
    return command


def _ensure_dist_writable(root: Path) -> None:
    """Fail early with a clear message if a previous build is still locked."""
    dist_dir = root / "dist" / "GimbalStudio"
    if not dist_dir.exists():
        return
    probe = dist_dir / ".pack_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return
    except OSError:
        pass

    try:
        shutil.rmtree(dist_dir)
    except OSError as exc:
        raise SystemExit(
            "无法清理旧的打包输出目录，通常是因为 GimbalStudio 仍在运行，"
            "或资源管理器/杀毒软件占用了 dist\\GimbalStudio。\n"
            "请先关闭程序后再执行: python scripts/pack.py\n"
            f"详情: {exc}"
        ) from exc


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    _ensure_dist_writable(root)
    subprocess.check_call(build_pyinstaller_command(sys.executable, root), cwd=root)


if __name__ == "__main__":
    main()
