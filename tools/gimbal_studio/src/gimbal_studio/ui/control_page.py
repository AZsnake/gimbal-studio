from __future__ import annotations

from collections.abc import Iterable, Mapping

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gimbal_studio.project.models import Project, SteerChannel, enabled_steers
from gimbal_studio.protocol.commands import build_move, build_stop
from gimbal_studio.serial_io.port import SerialLink, SerialLinkError
from gimbal_studio.ui.pad_widget import PadWidget


class ControlPage(QWidget):
    pose_changed = Signal(object)

    def __init__(
        self,
        serial_link: SerialLink,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.serial_link = serial_link
        self.project = Project()
        self.channels: list[SteerChannel] = []
        self.sliders: dict[int, QSlider] = {}
        self.spin_boxes: dict[int, QSpinBox] = {}
        self._pending_moves: dict[int, int] = {}
        self._applying_pose = False

        self._send_timer = QTimer(self)
        self._send_timer.setSingleShot(True)
        self._send_timer.setInterval(30)
        self._send_timer.timeout.connect(self._flush_pending_moves)
        self.serial_link.connection_changed.connect(self._on_connection_changed)

        self._build_ui()
        self._install_key_filters()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _install_key_filters(self) -> None:
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(28)

        pad_panel = QFrame()
        pad_layout = QVBoxLayout(pad_panel)
        pad_title = QLabel("二维控制盘")
        pad_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pad = PadWidget()
        self.pad.value_changed.connect(self._on_pad_changed)
        pad_layout.addWidget(pad_title)
        pad_layout.addWidget(self.pad, 1)

        controls_panel = QFrame()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.addWidget(QLabel("通道控制"))
        self.channel_form = QFormLayout()
        self.channel_form.setSpacing(12)
        controls_layout.addLayout(self.channel_form)
        controls_layout.addStretch(1)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Time"))
        self.time_spin = QSpinBox()
        self.time_spin.setRange(0, 9999)
        self.time_spin.setValue(1000)
        self.time_spin.setSuffix(" ms")
        time_row.addWidget(self.time_spin, 1)
        controls_layout.addLayout(time_row)

        button_row = QHBoxLayout()
        self.center_button = QPushButton("归中")
        self.center_button.clicked.connect(self.center)
        self.stop_button = QPushButton("急停")
        self.stop_button.setObjectName("emergencyButton")
        self.stop_button.clicked.connect(self.emergency_stop)
        button_row.addWidget(self.center_button)
        button_row.addWidget(self.stop_button)
        controls_layout.addLayout(button_row)

        layout.addWidget(pad_panel, 3)
        layout.addWidget(controls_panel, 2)

    def _adjust_channel(self, channel_index: int, delta: int) -> None:
        if len(self.channels) <= channel_index:
            return
        channel_id = self.channels[channel_index].id
        self._on_channel_changed(
            channel_id,
            self.spin_boxes[channel_id].value() + delta,
        )

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_map = {
                Qt.Key.Key_Left: (0, -10),
                Qt.Key.Key_Right: (0, 10),
                Qt.Key.Key_Down: (1, -10),
                Qt.Key.Key_Up: (1, 10),
            }
            adjustment = key_map.get(event.key())
            if adjustment is not None and len(self.channels) > adjustment[0]:
                self._adjust_channel(*adjustment)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def set_project(self, project: Project) -> None:
        self.project = project
        self.channels = enabled_steers(project)
        self._pending_moves.clear()
        self._send_timer.stop()
        self._clear_channel_rows()

        for channel in self.channels:
            minimum, maximum = sorted((channel.pmin, channel.pmax))
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(minimum, maximum)
            slider.setValue(max(minimum, min(maximum, 1500)))
            spin_box = QSpinBox()
            spin_box.setRange(minimum, maximum)
            spin_box.setValue(slider.value())
            slider.installEventFilter(self)
            spin_box.installEventFilter(self)

            slider.valueChanged.connect(
                lambda value, channel_id=channel.id: self._on_channel_changed(
                    channel_id, value
                )
            )
            spin_box.valueChanged.connect(
                lambda value, channel_id=channel.id: self._on_channel_changed(
                    channel_id, value
                )
            )

            row = QHBoxLayout()
            row.addWidget(slider, 1)
            row.addWidget(spin_box)
            self.channel_form.addRow(channel.title or f"通道 {channel.id}", row)
            self.sliders[channel.id] = slider
            self.spin_boxes[channel.id] = spin_box

        self.pad.setEnabled(len(self.channels) >= 2)
        self._sync_pad()
        self.pose_changed.emit(self.current_pose())

    def _clear_channel_rows(self) -> None:
        while self.channel_form.rowCount():
            self.channel_form.removeRow(0)
        self.sliders.clear()
        self.spin_boxes.clear()

    def current_pose(self) -> dict[int, int]:
        return {
            channel.id: self.spin_boxes[channel.id].value()
            for channel in self.channels
            if channel.id in self.spin_boxes
        }

    def apply_pose(
        self,
        moves: Mapping[int, int] | Iterable[tuple[int, int] | tuple[int, int, int]],
    ) -> None:
        if isinstance(moves, Mapping):
            pose = dict(moves)
            time_ms = None
        else:
            pose: dict[int, int] = {}
            time_ms: int | None = None
            for move in moves:
                channel_id, pwm = move[0], move[1]
                pose[channel_id] = pwm
                if len(move) >= 3:
                    time_ms = move[2]

        self._applying_pose = True
        try:
            for channel_id, pwm in pose.items():
                if channel_id in self.spin_boxes:
                    self._set_channel_widgets(channel_id, pwm)
            if time_ms is not None:
                self.time_spin.setValue(time_ms)
        finally:
            self._applying_pose = False

        self._sync_pad()
        self.pose_changed.emit(self.current_pose())

    def _set_channel_widgets(self, channel_id: int, value: int) -> None:
        slider = self.sliders[channel_id]
        spin_box = self.spin_boxes[channel_id]
        value = max(slider.minimum(), min(slider.maximum(), int(value)))
        with QSignalBlocker(slider), QSignalBlocker(spin_box):
            slider.setValue(value)
            spin_box.setValue(value)

    def _on_channel_changed(self, channel_id: int, value: int) -> None:
        self._set_channel_widgets(channel_id, value)
        self._sync_pad()
        self.pose_changed.emit(self.current_pose())
        if not self._applying_pose and self.serial_link.is_connected:
            self._pending_moves[channel_id] = value
            if not self._send_timer.isActive():
                self._send_timer.start()

    def _on_connection_changed(self, connected: bool) -> None:
        if connected:
            return
        self._send_timer.stop()
        self._pending_moves.clear()

    def _on_pad_changed(self, x: float, y: float) -> None:
        if len(self.channels) < 2:
            return
        for channel, normalized in zip(self.channels[:2], (x, y), strict=True):
            minimum, maximum = sorted((channel.pmin, channel.pmax))
            value = round(minimum + (normalized + 1.0) * (maximum - minimum) / 2.0)
            self._on_channel_changed(channel.id, value)

    def _sync_pad(self) -> None:
        if len(self.channels) < 2:
            self.pad.set_value(0.0, 0.0)
            return
        normalized: list[float] = []
        for channel in self.channels[:2]:
            minimum, maximum = sorted((channel.pmin, channel.pmax))
            value = self.spin_boxes[channel.id].value()
            span = maximum - minimum
            normalized.append(0.0 if not span else 2.0 * (value - minimum) / span - 1.0)
        self.pad.set_value(normalized[0], normalized[1])

    def center(self) -> None:
        for channel in self.channels:
            if channel.id not in self.sliders:
                continue
            slider = self.sliders[channel.id]
            value = max(slider.minimum(), min(slider.maximum(), 1500))
            self._on_channel_changed(channel.id, value)

    def emergency_stop(self) -> None:
        self._send_timer.stop()
        self._pending_moves.clear()
        if not self.serial_link.is_connected:
            return
        try:
            self.serial_link.send_text(build_stop())
        except SerialLinkError:
            return

    def _flush_pending_moves(self) -> None:
        pending, self._pending_moves = self._pending_moves, {}
        if not self.serial_link.is_connected:
            return
        for channel_id, pwm in pending.items():
            try:
                self.serial_link.send_text(
                    build_move(channel_id, pwm, self.time_spin.value())
                )
            except SerialLinkError:
                return

    def keyPressEvent(self, event) -> None:
        key_map = {
            Qt.Key.Key_Left: (0, -10),
            Qt.Key.Key_Right: (0, 10),
            Qt.Key.Key_Down: (1, -10),
            Qt.Key.Key_Up: (1, 10),
        }
        adjustment = key_map.get(event.key())
        if adjustment is None or len(self.channels) <= adjustment[0]:
            super().keyPressEvent(event)
            return
        channel_id = self.channels[adjustment[0]].id
        self._on_channel_changed(
            channel_id,
            self.spin_boxes[channel_id].value() + adjustment[1],
        )
        event.accept()
