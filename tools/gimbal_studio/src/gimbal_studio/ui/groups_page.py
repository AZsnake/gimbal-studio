from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gimbal_studio.project.ini_io import group_command
from gimbal_studio.project.models import ActionGroup, Project
from gimbal_studio.protocol.commands import build_clear_boot, build_set_boot
from gimbal_studio.ui.runner import SequenceRunner, TextLink


class GroupsPage(QWidget):
    pose_requested = Signal(object)

    def __init__(self, link: TextLink, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.link = link
        self.project = Project()
        self.runner = SequenceRunner(link, self)
        self._current_pose: dict[int, int] = {}
        self._current_time = 1000
        self._clipboard: ActionGroup | None = None
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        edit_row = QHBoxLayout()
        self.add_button = QPushButton("新增")
        self.insert_button = QPushButton("插入")
        self.delete_button = QPushButton("删除")
        self.copy_button = QPushButton("复制")
        self.paste_button = QPushButton("粘贴")
        for button in (
            self.add_button,
            self.insert_button,
            self.delete_button,
            self.copy_button,
            self.paste_button,
        ):
            edit_row.addWidget(button)
        edit_row.addStretch(1)
        layout.addLayout(edit_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["组号", "动作指令"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        run_row = QHBoxLayout()
        self.start_spin = QSpinBox()
        self.end_spin = QSpinBox()
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 9999)
        self.count_spin.setValue(1)
        run_row.addWidget(QLabel("起始"))
        run_row.addWidget(self.start_spin)
        run_row.addWidget(QLabel("结束"))
        run_row.addWidget(self.end_spin)
        run_row.addWidget(QLabel("次数"))
        run_row.addWidget(self.count_spin)

        self.online_button = QPushButton("在线运行")
        self.offline_button = QPushButton("脱机运行")
        self.download_button = QPushButton("下载")
        self.set_boot_button = QPushButton("设为开机动作")
        self.clear_boot_button = QPushButton("清除开机动作")
        self.cancel_button = QPushButton("取消")
        for button in (
            self.online_button,
            self.offline_button,
            self.download_button,
            self.set_boot_button,
            self.clear_boot_button,
            self.cancel_button,
        ):
            run_row.addWidget(button)
        layout.addLayout(run_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        self.add_button.clicked.connect(self.add_group)
        self.insert_button.clicked.connect(self.insert_group)
        self.delete_button.clicked.connect(self.delete_group)
        self.copy_button.clicked.connect(self.copy_group)
        self.paste_button.clicked.connect(self.paste_group)
        self.table.cellClicked.connect(self._select_group)
        self.table.cellDoubleClicked.connect(self._send_group)
        self.online_button.clicked.connect(self._run_online)
        self.offline_button.clicked.connect(self._run_offline)
        self.download_button.clicked.connect(self._download)
        self.set_boot_button.clicked.connect(self._set_boot)
        self.clear_boot_button.clicked.connect(self._clear_boot)
        self.cancel_button.clicked.connect(self.runner.cancel)
        self.runner.progress.connect(
            lambda current, total: self.status_label.setText(f"{current}/{total}")
        )
        self.runner.finished.connect(
            lambda mode: self.status_label.setText(f"完成: {mode}")
        )
        self.runner.failed.connect(
            lambda message: self.status_label.setText(f"失败: {message}")
        )

    def set_project(self, project: Project) -> None:
        self.runner.cancel()
        self.project = project
        self._clipboard = None
        self.refresh()

    def set_current_pose(self, pose: dict[int, int], time_ms: int = 1000) -> None:
        self._current_pose = dict(pose)
        self._current_time = max(0, min(9999, int(time_ms)))

    def refresh(self) -> None:
        self.table.setRowCount(len(self.project.groups))
        for row, group in enumerate(self.project.groups):
            self.table.setItem(row, 0, QTableWidgetItem(f"G{group.index:04d}"))
            self.table.setItem(row, 1, QTableWidgetItem(group_command(group)))
        maximum = max(0, len(self.project.groups) - 1)
        self.start_spin.setRange(0, maximum)
        self.end_spin.setRange(0, maximum)
        self.end_spin.setValue(maximum)
        enabled = bool(self.project.groups)
        for button in (
            self.online_button,
            self.offline_button,
            self.download_button,
            self.set_boot_button,
        ):
            button.setEnabled(enabled)

    def _selected_row(self) -> int | None:
        row = self.table.currentRow()
        return row if 0 <= row < len(self.project.groups) else None

    def _moves_from_pose(self) -> list[tuple[int, int, int]]:
        return [
            (channel_id, pwm, self._current_time)
            for channel_id, pwm in sorted(self._current_pose.items())
        ]

    def _reindex_and_refresh(self, selected_row: int | None = None) -> None:
        for index, group in enumerate(self.project.groups):
            group.index = index
        self.refresh()
        if selected_row is not None and self.project.groups:
            self.table.selectRow(min(selected_row, len(self.project.groups) - 1))

    def add_group(self) -> None:
        row = len(self.project.groups)
        self.project.groups.append(ActionGroup(row, self._moves_from_pose()))
        self._reindex_and_refresh(row)

    def insert_group(self) -> None:
        row = self._selected_row()
        if row is None:
            row = len(self.project.groups)
        self.project.groups.insert(row, ActionGroup(row, self._moves_from_pose()))
        self._reindex_and_refresh(row)

    def delete_group(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        del self.project.groups[row]
        self._reindex_and_refresh(row)

    def copy_group(self) -> None:
        row = self._selected_row()
        if row is not None:
            self._clipboard = deepcopy(self.project.groups[row])

    def paste_group(self) -> None:
        row = self._selected_row()
        if row is None or self._clipboard is None:
            return
        self.project.groups[row] = ActionGroup(
            index=row,
            moves=deepcopy(self._clipboard.moves),
        )
        self._reindex_and_refresh(row)

    def _select_group(self, row: int, _column: int) -> None:
        if 0 <= row < len(self.project.groups):
            self.pose_requested.emit(list(self.project.groups[row].moves))

    def _send_group(self, row: int, _column: int) -> None:
        if not 0 <= row < len(self.project.groups):
            return
        try:
            self.link.send_text(group_command(self.project.groups[row]))
        except Exception as exc:
            self.status_label.setText(f"失败: {exc}")

    def _range(self) -> tuple[int, int, int]:
        return self.start_spin.value(), self.end_spin.value(), self.count_spin.value()

    def _run_online(self) -> None:
        start, end, count = self._range()
        self.runner.run_online(self.project.groups, start, end, count)

    def _run_offline(self) -> None:
        self.runner.run_offline(*self._range())

    def _download(self) -> None:
        self.runner.download(self.project.groups, self.start_spin.value())

    def _set_boot(self) -> None:
        try:
            self.link.send_text(build_set_boot(*self._range()))
        except Exception as exc:
            self.status_label.setText(f"失败: {exc}")

    def _clear_boot(self) -> None:
        try:
            self.link.send_text(build_clear_boot())
        except Exception as exc:
            self.status_label.setText(f"失败: {exc}")
