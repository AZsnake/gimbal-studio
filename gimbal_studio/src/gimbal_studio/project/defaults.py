from pathlib import Path

from gimbal_studio.project.ini_io import save_ini
from gimbal_studio.project.models import ActionGroup, Project, SteerChannel

# Showcase: fast, wide, multi-motif (pan, tilt, time_ms). Band ~650–2350.
_SHOWCASE_GROUPS: tuple[tuple[int, int, int], ...] = (
    # Snap open
    (1500, 1500, 180),
    (1500, 780, 280),
    # Wide clockwise orbit (8 points)
    (1050, 850, 260),
    (700, 1500, 320),
    (900, 2150, 280),
    (1500, 2320, 300),
    (2100, 2150, 280),
    (2300, 1500, 320),
    (2100, 850, 280),
    (1500, 680, 260),
    # Zigzag ladder down
    (800, 1000, 220),
    (2200, 1200, 240),
    (800, 1400, 220),
    (2200, 1600, 240),
    (800, 1800, 220),
    (2200, 2000, 240),
    # Dense figure-8
    (1900, 900, 200),
    (1100, 2100, 260),
    (1100, 900, 240),
    (1900, 2100, 260),
    (1900, 900, 220),
    # Counter-orbit slice (CCW partial)
    (2300, 1200, 250),
    (1800, 2200, 250),
    (700, 1800, 280),
    (700, 900, 250),
    # Corner punches
    (650, 700, 300),
    (2350, 700, 320),
    (2350, 2300, 320),
    (650, 2300, 320),
    # Whip pan + settle
    (2350, 1500, 350),
    (650, 1500, 380),
    (1500, 1500, 400),
)


def default_project() -> Project:
    steers = [
        SteerChannel(
            title="水平",
            id=0,
            pmin=500,
            pmax=2500,
            lab_left="左",
            lab_right="右",
            enable=True,
            x=200,
            y=350,
        ),
        SteerChannel(
            title="倾斜",
            id=1,
            pmin=500,
            pmax=2500,
            lab_left="仰",
            lab_right="俯",
            enable=True,
            x=200,
            y=200,
        ),
    ]
    groups = [
        ActionGroup(
            index=index,
            moves=[(0, pan, time_ms), (1, tilt, time_ms)],
        )
        for index, (pan, tilt, time_ms) in enumerate(_SHOWCASE_GROUPS)
    ]
    return Project(
        steers=steers,
        groups=groups,
        meta={
            "zide_version": "Zide V5.99",
            "timeDownload": "300",
            "bg_index": "0",
        },
    )


def ensure_default_config(path: Path) -> Path:
    """Write the showcase project to ``path`` if missing; return resolved path."""
    target = path.resolve()
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        save_ini(default_project(), target)
    return target
