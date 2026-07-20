from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gimbal_studio.serial_io.port import SerialLink, SerialLinkError, list_ports
from gimbal_studio.ui.log_page import LogPage


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gimbal Studio")
        self.resize(1100, 720)

        self.serial_link = SerialLink(self)
        self._build_ui()
        self._connect_signals()
        self.refresh_ports()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(18, 12, 18, 12)

        self.brand_label = QLabel("Gimbal Studio")
        self.brand_label.setObjectName("brandLabel")
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(120)
        self.refresh_button = QPushButton("刷新")
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("115200")
        self.connect_button = QPushButton("连接")
        self.connect_button.setObjectName("connectButton")
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setProperty("connected", False)
        self.status_dot.setToolTip("未连接")

        top_layout.addWidget(self.brand_label)
        top_layout.addStretch(1)
        top_layout.addWidget(QLabel("端口"))
        top_layout.addWidget(self.port_combo)
        top_layout.addWidget(self.refresh_button)
        top_layout.addWidget(QLabel("波特率"))
        top_layout.addWidget(self.baud_combo)
        top_layout.addWidget(self.connect_button)
        top_layout.addWidget(self.status_dot)

        self.tabs = QTabWidget()
        control_placeholder = QLabel("控制页面将在 Task 7 实现")
        control_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        groups_placeholder = QLabel("动作组页面将在 Task 8 实现")
        groups_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.log_page = LogPage()
        self.tabs.addTab(control_placeholder, "控制")
        self.tabs.addTab(groups_placeholder, "动作组")
        self.tabs.addTab(self.log_page, "串口日志")

        root_layout.addWidget(top_bar)
        root_layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self.refresh_ports)
        self.connect_button.clicked.connect(self._toggle_connection)
        self.log_page.submit_command.connect(self._send_command)
        self.serial_link.received.connect(self.log_page.append_received)
        self.serial_link.connection_changed.connect(self._set_connected)
        self.serial_link.error_occurred.connect(self.log_page.append_error)

    def refresh_ports(self) -> None:
        selected = self.port_combo.currentText()
        ports = list_ports()
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if selected in ports:
            self.port_combo.setCurrentText(selected)
        self.connect_button.setEnabled(bool(ports) or self.serial_link.is_connected)

    def _toggle_connection(self) -> None:
        if self.serial_link.is_connected:
            self.serial_link.disconnect()
            return

        port = self.port_combo.currentText()
        if not port:
            self.log_page.append_error("未找到可用串口")
            return
        try:
            self.serial_link.connect(port, int(self.baud_combo.currentText()))
        except SerialLinkError:
            return

    def _send_command(self, command: str) -> None:
        try:
            self.serial_link.send_text(command)
        except SerialLinkError:
            return
        self.log_page.append_sent(command)

    def _set_connected(self, connected: bool) -> None:
        self.connect_button.setText("断开" if connected else "连接")
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.refresh_button.setEnabled(not connected)
        self.status_dot.setProperty("connected", connected)
        self.status_dot.setToolTip("已连接" if connected else "未连接")
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        if not connected:
            self.connect_button.setEnabled(bool(self.port_combo.count()))

    def closeEvent(self, event) -> None:
        self.serial_link.disconnect()
        super().closeEvent(event)
