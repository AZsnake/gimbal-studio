import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from gimbal_studio.ui.main_window import MainWindow


def load_theme() -> str:
    theme_path = Path(__file__).with_name("resources") / "theme.qss"
    return theme_path.read_text(encoding="utf-8")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Gimbal Studio")
    app.setStyleSheet(load_theme())
    win = MainWindow()
    win.show()
    return app.exec()
