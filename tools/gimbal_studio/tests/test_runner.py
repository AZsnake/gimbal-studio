import time

from PySide6.QtCore import QCoreApplication

from gimbal_studio.project.models import ActionGroup
from gimbal_studio.ui.runner import SequenceRunner

APP = QCoreApplication.instance() or QCoreApplication([])


class RecordingLink:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send_text(self, data: str) -> None:
        self.sent.append(data)


def wait_until(predicate, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        APP.processEvents()
        time.sleep(0.001)
    assert predicate()


def test_offline_sends_one_dgt_command() -> None:
    link = RecordingLink()
    runner = SequenceRunner(link)

    runner.run_offline(0, 4, 1)

    assert link.sent == ["$DGT:0-4,1!"]


def test_online_blocking_sends_selected_groups_for_each_repetition() -> None:
    link = RecordingLink()
    runner = SequenceRunner(link)
    groups = [
        ActionGroup(0, [(0, 1500, 50), (1, 1500, 50)]),
        ActionGroup(1, [(0, 1100, 50), (1, 1500, 50)]),
        ActionGroup(2, [(0, 900, 50), (1, 1500, 50)]),
    ]

    runner.run_online_blocking(groups, 1, 2, 2)

    assert link.sent == [
        "{#000P1100T0050!#001P1500T0050!}",
        "{#000P0900T0050!#001P1500T0050!}",
        "{#000P1100T0050!#001P1500T0050!}",
        "{#000P0900T0050!#001P1500T0050!}",
    ]


def test_online_runs_asynchronously_and_reports_progress() -> None:
    link = RecordingLink()
    runner = SequenceRunner(link)
    groups = [
        ActionGroup(0, [(0, 1500, 0)]),
        ActionGroup(1, [(0, 1100, 0)]),
    ]
    progress: list[tuple[int, int]] = []
    finished: list[str] = []
    runner.progress.connect(lambda current, total: progress.append((current, total)))
    runner.finished.connect(finished.append)

    runner.run_online(groups, 0, 1, 2)
    wait_until(lambda: bool(finished))

    assert link.sent == [
        "{#000P1500T0000!}",
        "{#000P1100T0000!}",
        "{#000P1500T0000!}",
        "{#000P1100T0000!}",
    ]
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert finished == ["online"]


def test_download_starts_at_requested_index() -> None:
    link = RecordingLink()
    runner = SequenceRunner(link)
    groups = [
        ActionGroup(0, [(0, 1500, 50)]),
        ActionGroup(1, [(0, 1100, 50)]),
        ActionGroup(2, [(0, 900, 50)]),
    ]
    finished: list[str] = []
    runner.finished.connect(finished.append)

    runner.download(groups, from_index=1, inter_frame_ms=0)
    wait_until(lambda: bool(finished))

    assert link.sent == [
        "{#000P1100T0050!}",
        "{#000P0900T0050!}",
    ]
    assert finished == ["download"]


def test_cancel_from_progress_emits_single_finished_signal() -> None:
    link = RecordingLink()
    runner = SequenceRunner(link)
    groups = [
        ActionGroup(0, [(0, 1500, 50)]),
        ActionGroup(1, [(0, 1100, 50)]),
    ]
    finished: list[str] = []
    runner.finished.connect(finished.append)
    runner.progress.connect(lambda _current, _total: runner.cancel())

    runner.run_online(groups, 0, 1, 1)

    assert link.sent == ["{#000P1500T0050!}"]
    assert finished == ["cancelled"]


def test_cancel_stops_an_active_download() -> None:
    link = RecordingLink()
    runner = SequenceRunner(link)
    groups = [
        ActionGroup(0, [(0, 1500, 50)]),
        ActionGroup(1, [(0, 1100, 50)]),
    ]
    finished: list[str] = []
    runner.finished.connect(finished.append)

    runner.download(groups, from_index=0, inter_frame_ms=1000)
    runner.cancel()

    assert link.sent == ["{#000P1500T0050!}"]
    assert finished == ["cancelled"]


def test_send_error_emits_failed_and_stops_session() -> None:
    class FailingLink(RecordingLink):
        def send_text(self, data: str) -> None:
            raise RuntimeError("write failed")

    runner = SequenceRunner(FailingLink())
    failures: list[str] = []
    finished: list[str] = []
    runner.failed.connect(failures.append)
    runner.finished.connect(finished.append)

    runner.download([ActionGroup(0, [(0, 1500, 50)])], 0, 0)

    assert failures == ["write failed"]
    assert finished == []
