from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LogPage(QWidget):
    submit_command = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("通信收发内容将显示在这里")

        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("输入通信命令")
        self.send_button = QPushButton("发送")
        self.clear_button = QPushButton("清空")

        command_row = QHBoxLayout()
        command_row.addWidget(self.command_input, 1)
        command_row.addWidget(self.send_button)
        command_row.addWidget(self.clear_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.log_output, 1)
        layout.addLayout(command_row)

        self.command_input.returnPressed.connect(self._submit)
        self.send_button.clicked.connect(self._submit)
        self.clear_button.clicked.connect(self.log_output.clear)

    def append_received(self, text: str) -> None:
        self._append("RX", text)

    def append_sent(self, text: str) -> None:
        self._append("TX", text)

    def append_error(self, text: str) -> None:
        self._append("ERR", text)

    def append_info(self, text: str) -> None:
        self._append("INF", text)

    def _submit(self) -> None:
        command = self.command_input.text()
        if not command:
            return
        self.submit_command.emit(command)
        self.command_input.clear()

    def _append(self, direction: str, text: str) -> None:
        lines = text.rstrip("\r\n").splitlines() or [""]
        for line in lines:
            self.log_output.appendPlainText(f"{direction}  {line}")
