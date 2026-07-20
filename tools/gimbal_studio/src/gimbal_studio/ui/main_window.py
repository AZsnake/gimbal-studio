from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gimbal_studio.project.ini_io import load_ini, save_ini
from gimbal_studio.project.models import Project, SteerChannel
from gimbal_studio.serial_io.port import SerialLink, SerialLinkError, list_ports
from gimbal_studio.ui.control_page import ControlPage
from gimbal_studio.ui.groups_page import GroupsPage
from gimbal_studio.ui.log_page import LogPage


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gimbal Studio")
        self.resize(1100, 720)

        self.project = self._default_project()
        self.current_path: Path | None = None
        self.serial_link = SerialLink(self)
        self._build_ui()
        self._connect_signals()
        self.refresh_ports()
        self._set_connected(False)

    @staticmethod
    def _default_project() -> Project:
        return Project(
            steers=[
                SteerChannel(
                    title="水平", id=0, pmin=500, pmax=2500, enable=True
                ),
                SteerChannel(
                    title="倾斜", id=1, pmin=500, pmax=2500, enable=True
                ),
            ]
        )

    def _build_ui(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        self.open_action = QAction("打开…", self)
        self.save_action = QAction("保存", self)
        self.save_as_action = QAction("另存为…", self)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)

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
        self.control_page = ControlPage(self.serial_link)
        self.groups_page = GroupsPage(self.serial_link)
        self.control_page.set_project(self.project)
        self.groups_page.set_project(self.project)
        self.groups_page.set_current_pose(
            self.control_page.current_pose(),
            self.control_page.time_spin.value(),
        )
        self.log_page = LogPage()
        self.tabs.addTab(self.control_page, "控制")
        self.tabs.addTab(self.groups_page, "动作组")
        self.tabs.addTab(self.log_page, "串口日志")

        root_layout.addWidget(top_bar)
        root_layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self.refresh_ports)
        self.connect_button.clicked.connect(self._toggle_connection)
        self.open_action.triggered.connect(self.open_project)
        self.save_action.triggered.connect(self.save_project)
        self.save_as_action.triggered.connect(self.save_project_as)
        self.log_page.submit_command.connect(self._send_command)
        self.groups_page.pose_requested.connect(self.control_page.apply_pose)
        self.control_page.pose_changed.connect(
            lambda pose: self.groups_page.set_current_pose(
                pose,
                self.control_page.time_spin.value(),
            )
        )
        self.control_page.time_spin.valueChanged.connect(
            lambda time_ms: self.groups_page.set_current_pose(
                self.control_page.current_pose(),
                time_ms,
            )
        )
        self.groups_page.start_spin.valueChanged.connect(
            lambda: self._update_sequence_actions()
        )
        self.groups_page.end_spin.valueChanged.connect(
            lambda: self._update_sequence_actions()
        )
        self.serial_link.received.connect(self.log_page.append_received)
        self.serial_link.connection_changed.connect(self._set_connected)
        self.serial_link.error_occurred.connect(self.log_page.append_error)

    def set_project(self, project: Project, path: Path | None = None) -> None:
        self.groups_page.runner.cancel()
        self.project = project
        self.current_path = path
        self.control_page.set_project(project)
        self.groups_page.set_project(project)
        self.groups_page.set_current_pose(
            self.control_page.current_pose(),
            self.control_page.time_spin.value(),
        )
        self._update_sequence_actions()
        self._update_title()

    def _update_title(self) -> None:
        suffix = f" — {self.current_path.name}" if self.current_path else ""
        self.setWindowTitle(f"Gimbal Studio{suffix}")

    def open_project(self) -> None:
        filename, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "打开工程",
            str(self.current_path.parent if self.current_path else Path.cwd()),
            "INI 工程 (*.ini);;所有文件 (*)",
        )
        if not filename:
            return
        path = Path(filename)
        try:
            project = load_ini(path)
        except (OSError, UnicodeError, ValueError) as exc:
            self.log_page.append_error(f"打开工程失败: {exc}")
            return
        self.set_project(project, path)

    def save_project(self) -> None:
        if self.current_path is None:
            self.save_project_as()
            return
        self._save_to(self.current_path)

    def save_project_as(self) -> None:
        filename, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "保存工程",
            str(self.current_path or Path.cwd() / "config_bes.ini"),
            "INI 工程 (*.ini);;所有文件 (*)",
        )
        if filename:
            self._save_to(Path(filename))

    def _save_to(self, path: Path) -> None:
        try:
            save_ini(self.project, path)
        except OSError as exc:
            self.log_page.append_error(f"保存工程失败: {exc}")
            return
        self.current_path = path
        self._update_title()

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
        except SerialLinkError as exc:
            self._set_connected(False)
            QMessageBox.critical(self, "连接失败", str(exc))
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
            self.groups_page.runner.cancel()
            self.connect_button.setEnabled(bool(self.port_combo.count()))
        self._update_sequence_actions(connected)

    def _update_sequence_actions(self, connected: bool | None = None) -> None:
        if connected is None:
            connected = self.serial_link.is_connected
        enabled = (
            connected
            and bool(self.project.groups)
            and self.groups_page._is_range_valid()
        )
        for button in (
            self.groups_page.online_button,
            self.groups_page.offline_button,
            self.groups_page.download_button,
        ):
            button.setEnabled(enabled)

    def closeEvent(self, event) -> None:
        self.groups_page.runner.cancel()
        self.serial_link.disconnect()
        super().closeEvent(event)
