from collections.abc import Sequence
from typing import Protocol

from PySide6.QtCore import QObject, QTimer, Signal

from gimbal_studio.project.ini_io import group_command
from gimbal_studio.project.models import ActionGroup
from gimbal_studio.protocol.commands import build_dgt


class TextLink(Protocol):
    def send_text(self, data: str) -> None: ...


class SequenceRunner(QObject):
    progress = Signal(int, int)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, link: TextLink, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._link = link
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._send_next)
        self._pending: list[tuple[str, int]] = []
        self._sent_count = 0
        self._mode: str | None = None
        self._session_id = 0

    def run_online(
        self,
        groups: list[ActionGroup],
        start: int,
        end: int,
        count: int,
    ) -> None:
        selected = groups[start : end + 1]
        frames = [
            (group_command(group), self._group_duration(group))
            for _ in range(count)
            for group in selected
        ]
        self._start_session("online", frames)

    def run_offline(self, start: int, end: int, count: int) -> None:
        self._start_session("offline", [(build_dgt(start, end, count), 0)])

    def run_online_blocking(
        self,
        groups: list[ActionGroup],
        start: int,
        end: int,
        count: int,
    ) -> None:
        selected = groups[start : end + 1]
        commands = [
            group_command(group)
            for _ in range(count)
            for group in selected
        ]
        self._session_id += 1
        session_id = self._session_id
        self._stop_session()
        total = len(commands)
        for current, command in enumerate(commands, start=1):
            try:
                self._link.send_text(command)
            except Exception as exc:
                self.failed.emit(str(exc))
                return
            self.progress.emit(current, total)
            if session_id != self._session_id:
                return
        self.finished.emit("online")

    def download(
        self,
        groups: list[ActionGroup],
        from_index: int,
        inter_frame_ms: int = 300,
    ) -> None:
        # If Zide captures differ, only the frame construction here needs changing.
        frames = [
            (group_command(group), inter_frame_ms)
            for group in groups[from_index:]
        ]
        self._start_session("download", frames)

    def cancel(self) -> None:
        self._session_id += 1
        if self._mode is None:
            return
        self._stop_session()
        self.finished.emit("cancelled")

    @staticmethod
    def _group_duration(group: ActionGroup) -> int:
        return max((time_ms for _, _, time_ms in group.moves), default=0)

    def _start_session(
        self,
        mode: str,
        frames: Sequence[tuple[str, int]],
    ) -> None:
        self._session_id += 1
        self._stop_session()
        self._mode = mode
        self._pending = list(frames)
        self._sent_count = 0
        if not self._pending:
            self._stop_session()
            self.finished.emit(mode)
            return
        self._send_next()

    def _send_next(self) -> None:
        session_id = self._session_id
        if self._mode is None or not self._pending:
            return

        command, delay_ms = self._pending.pop(0)
        try:
            self._link.send_text(command)
        except Exception as exc:
            self._stop_session()
            self.failed.emit(str(exc))
            return

        self._sent_count += 1
        self.progress.emit(self._sent_count, self._sent_count + len(self._pending))
        if session_id != self._session_id:
            return
        if not self._pending:
            mode = self._mode
            self._stop_session()
            self.finished.emit(mode)
            return
        self._timer.start(max(0, delay_ms))

    def _stop_session(self) -> None:
        self._timer.stop()
        self._pending.clear()
        self._sent_count = 0
        self._mode = None
