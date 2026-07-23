from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, QSettings, QSize
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
from gimbal_studio.project.startup import (
    get_last_project_path,
    resolve_startup_path,
    set_last_project_path,
)
from gimbal_studio.transport.errors import TransportError
from gimbal_studio.transport.router import TransportRouter
from gimbal_studio.ui.control_page import ControlPage
from gimbal_studio.ui.groups_page import GroupsPage
from gimbal_studio.ui.log_page import LogPage

# Common UART baud rates; default remains 115200 for this board.
_BAUD_RATES = (
    "1200",
    "2400",
    "4800",
    "9600",
    "14400",
    "19200",
    "38400",
    "57600",
    "115200",
    "230400",
    "460800",
    "921600",
)
_DEFAULT_BAUD = "115200"
_PAD_FOCUS_SIZE = QSize(360, 360)


class MainWindow(QMainWindow):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        settings_store: QSettings | None = None,
        autoload: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gimbal Studio")
        self.resize(1100, 720)

        self._settings = settings_store
        self.project = self._default_project()
        self.current_path: Path | None = None
        # Keep attribute name for existing tests/call sites.
        self.serial_link = TransportRouter(self)
        self._hid_by_display: dict[str, Any] = {}
        self._pad_focus = False
        self._saved_geometry: QRect | None = None
        self._saved_maximized = False
        self._pad_home: QWidget | None = None
        self._build_ui()
        self._connect_signals()
        self.refresh_ports()
        self._set_connected(False)
        if autoload:
            self._load_startup_project()

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

    def _load_startup_project(self) -> None:
        last = get_last_project_path(self._settings)
        path = resolve_startup_path(Path.cwd(), last or None)
        try:
            project = load_ini(path)
        except (OSError, UnicodeError, ValueError) as exc:
            self.log_page.append_error(f"启动加载工程失败: {exc}")
            try:
                from gimbal_studio.project.defaults import ensure_default_config

                fallback = ensure_default_config(Path.cwd() / "config.ini")
                project = load_ini(fallback)
                path = fallback
            except (OSError, UnicodeError, ValueError) as nested:
                self.log_page.append_error(f"创建默认工程失败: {nested}")
                from gimbal_studio.project.defaults import default_project

                self.set_project(default_project(), None)
                return
        self.set_project(project, path)
        set_last_project_path(path, self._settings)

    def _build_ui(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        self.open_action = QAction("打开…", self)
        self.save_action = QAction("保存", self)
        self.save_as_action = QAction("另存为…", self)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)

        view_menu = self.menuBar().addMenu("视图")
        self.pad_focus_action = QAction("专注控制盘", self)
        self.pad_focus_action.setCheckable(True)
        view_menu.addAction(self.pad_focus_action)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.top_bar = QFrame()
        self.top_bar.setObjectName("topBar")
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(18, 12, 18, 12)

        self.brand_label = QLabel("Gimbal Studio")
        self.brand_label.setObjectName("brandLabel")
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(180)
        self.port_combo.setEditable(True)
        self.port_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.port_combo.setPlaceholderText("例如 COM3 或 HID 设备")
        self.refresh_button = QPushButton("刷新")
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(list(_BAUD_RATES))
        self.baud_combo.setCurrentText(_DEFAULT_BAUD)
        self.baud_combo.setMinimumWidth(100)
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
        self.tabs.addTab(self.log_page, "通信日志")

        self.pad_focus_host = QWidget()
        self.pad_focus_host.hide()
        focus_layout = QVBoxLayout(self.pad_focus_host)
        focus_layout.setContentsMargins(8, 8, 8, 8)
        focus_layout.setSpacing(4)
        exit_row = QHBoxLayout()
        exit_row.addStretch(1)
        self.exit_pad_focus_button = QPushButton("退出专注")
        exit_row.addWidget(self.exit_pad_focus_button)
        focus_layout.addLayout(exit_row)
        self._pad_focus_pad_layout = QVBoxLayout()
        focus_layout.addLayout(self._pad_focus_pad_layout, 1)

        root_layout.addWidget(self.top_bar)
        root_layout.addWidget(self.tabs, 1)
        root_layout.addWidget(self.pad_focus_host, 1)
        self.setCentralWidget(root)

    def is_pad_focus(self) -> bool:
        return self._pad_focus

    def set_pad_focus(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._pad_focus:
            self.pad_focus_action.setChecked(enabled)
            return

        pad = self.control_page.pad
        if enabled:
            self._saved_maximized = self.isMaximized()
            self._saved_geometry = self.geometry()
            self._pad_home = pad.parentWidget()
            if self._pad_home is not None and self._pad_home.layout() is not None:
                self._pad_home.layout().removeWidget(pad)
            self._pad_focus_pad_layout.addWidget(pad, 1)

            self.menuBar().hide()
            self.top_bar.hide()
            self.tabs.hide()
            self.pad_focus_host.show()

            if self._saved_maximized:
                self.showNormal()
            self.resize(_PAD_FOCUS_SIZE)
        else:
            self._pad_focus_pad_layout.removeWidget(pad)
            if self._pad_home is not None and self._pad_home.layout() is not None:
                self._pad_home.layout().addWidget(pad, 1)
            self._pad_home = None

            self.pad_focus_host.hide()
            self.tabs.show()
            self.top_bar.show()
            self.menuBar().show()

            if self._saved_maximized:
                self.showMaximized()
            elif self._saved_geometry is not None:
                self.setGeometry(self._saved_geometry)
            self._saved_geometry = None
            self._saved_maximized = False

        self._pad_focus = enabled
        self.pad_focus_action.blockSignals(True)
        self.pad_focus_action.setChecked(enabled)
        self.pad_focus_action.blockSignals(False)

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self.refresh_ports)
        self.connect_button.clicked.connect(self._toggle_connection)
        self.open_action.triggered.connect(self.open_project)
        self.save_action.triggered.connect(self.save_project)
        self.save_as_action.triggered.connect(self.save_project_as)
        self.pad_focus_action.toggled.connect(self.set_pad_focus)
        self.exit_pad_focus_button.clicked.connect(lambda: self.set_pad_focus(False))
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
        self.groups_page.actions_need_update.connect(self._update_sequence_actions)
        self.serial_link.received.connect(self.log_page.append_received)
        self.serial_link.connection_changed.connect(self._set_connected)
        self.serial_link.error_occurred.connect(self.log_page.append_error)
        self.serial_link.sent.connect(self.log_page.append_sent)
        self.port_combo.editTextChanged.connect(self._on_port_text_changed)
        self.port_combo.currentIndexChanged.connect(self._on_port_text_changed)

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
        set_last_project_path(path, self._settings)

    def save_project(self) -> None:
        if self.current_path is None:
            self.save_project_as()
            return
        self._save_to(self.current_path)

    def save_project_as(self) -> None:
        filename, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "保存工程",
            str(self.current_path or Path.cwd() / "config.ini"),
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
        set_last_project_path(path, self._settings)

    def refresh_ports(self) -> None:
        selected = self.port_combo.currentText().strip()
        serial_ports, hid_devices = TransportRouter.enumerate_devices()
        self._hid_by_display = {
            device["display"]: device["path"] for device in hid_devices
        }

        labels = [device["display"] for device in hid_devices] + list(serial_ports)
        self.port_combo.clear()
        self.port_combo.addItems(labels)

        if selected in labels:
            self.port_combo.setCurrentText(selected)
        elif selected:
            self.port_combo.setEditText(selected)
        elif labels:
            # Editable combo + placeholderText leaves index at -1 after addItems.
            self.port_combo.setCurrentIndex(0)
        self._on_port_text_changed()

    def _selected_is_hid(self) -> bool:
        text = self.port_combo.currentText().strip()
        return text in self._hid_by_display or text.startswith("HID:")

    def _on_port_text_changed(self, *_args: object) -> None:
        if not self.serial_link.is_connected:
            self.baud_combo.setEnabled(not self._selected_is_hid())
        self._update_connect_enabled()

    def _toggle_connection(self) -> None:
        if self.serial_link.is_connected:
            self.serial_link.disconnect()
            return

        selected = self.port_combo.currentText().strip()
        if not selected:
            self.log_page.append_error("未找到可用设备")
            return

        try:
            if selected in self._hid_by_display:
                self.serial_link.connect_hid(self._hid_by_display[selected])
            elif selected.startswith("HID:"):
                raise TransportError(
                    "HID 设备路径未知，请先点击“刷新”再连接"
                )
            else:
                self.serial_link.connect(
                    selected, int(self.baud_combo.currentText())
                )
        except TransportError as exc:
            self._set_connected(False)
            QMessageBox.critical(self, "连接失败", str(exc))
            return
        kind = "HID" if self._selected_is_hid() else "串口"
        self.log_page.append_info(f"已连接 ({kind})，可拖动控制盘或发送指令")

    def _send_command(self, command: str) -> None:
        try:
            self.serial_link.send_text(command)
        except TransportError:
            return
        # TX is logged via serial_link.sent

    def _set_connected(self, connected: bool) -> None:
        self.connect_button.setText("断开" if connected else "连接")
        self.port_combo.setEnabled(not connected)
        self.refresh_button.setEnabled(not connected)
        if connected:
            self.baud_combo.setEnabled(False)
        else:
            self.baud_combo.setEnabled(not self._selected_is_hid())
        self.status_dot.setProperty("connected", connected)
        self.status_dot.setToolTip("已连接" if connected else "未连接")
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        if not connected:
            self.groups_page.runner.cancel()
            self._update_connect_enabled()
        self._update_sequence_actions(connected)

    def _update_connect_enabled(self) -> None:
        if self.serial_link.is_connected:
            return
        self.connect_button.setEnabled(
            bool(self.port_combo.count())
            or bool(self.port_combo.currentText().strip())
        )

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
