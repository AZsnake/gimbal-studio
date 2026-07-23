import sys
from importlib.resources import files

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from gimbal_studio.ui.main_window import MainWindow

_CJK_FONT_CANDIDATES = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "PingFang SC",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
)


def load_theme() -> str:
    theme_path = files("gimbal_studio") / "resources" / "theme.qss"
    return theme_path.read_text(encoding="utf-8")


def pick_ui_font(point_size: int = 10) -> QFont:
    """Prefer a CJK-capable face so Chinese glyphs share one metrics family."""
    available = set(QFontDatabase.families())
    for family in _CJK_FONT_CANDIDATES:
        if family in available:
            return QFont(family, point_size)
    return QFont("Segoe UI", point_size)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Gimbal Studio")
    app.setFont(pick_ui_font())
    app.setStyleSheet(load_theme())
    win = MainWindow()
    win.show()
    return app.exec()
