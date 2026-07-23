from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from gimbal_studio.project.defaults import ensure_default_config

_ORG = "STABLIZER"
_APP = "GimbalStudio"
_LAST_PATH_KEY = "last_project_path"


def settings() -> QSettings:
    return QSettings(_ORG, _APP)


def get_last_project_path(store: QSettings | None = None) -> str:
    value = (store or settings()).value(_LAST_PATH_KEY, "", type=str)
    return (value or "").strip()


def set_last_project_path(path: Path | str, store: QSettings | None = None) -> None:
    (store or settings()).setValue(_LAST_PATH_KEY, str(Path(path).resolve()))


def resolve_startup_path(
    cwd: Path | str,
    last_path: str | None,
) -> Path:
    """Pick startup INI: valid last path → cwd/config.ini → create default."""
    workdir = Path(cwd)
    if last_path:
        candidate = Path(last_path)
        if candidate.is_file():
            return candidate.resolve()
    local = workdir / "config.ini"
    if local.is_file():
        return local.resolve()
    return ensure_default_config(local)
