import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow


def main() -> int:
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("Gimbal Studio")
    win.setCentralWidget(QLabel("Gimbal Studio — scaffolding"))
    win.resize(960, 640)
    win.show()
    return app.exec()
