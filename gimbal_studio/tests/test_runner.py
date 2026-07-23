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


def test_online_sends_compact_group_commands() -> None:
    """Online execute must not flood HID with 32-slot padded frames."""
    link = RecordingLink()
    runner = SequenceRunner(link)
    groups = [
        ActionGroup(0, [(0, 1500, 50), (1, 1500, 50)]),
        ActionGroup(1, [(0, 1100, 50), (1, 1500, 50)]),
    ]
    finished: list[str] = []
    runner.finished.connect(finished.append)

    runner.run_online(groups, start=0, end=1, count=1)
    wait_until(lambda: finished == ["online"], timeout=1.5)

    assert link.sent == [
        "{#000P1500T0050!#001P1500T0050!}",
        "{#000P1100T0050!#001P1500T0050!}",
    ]
    assert all("#031P0000T0000!" not in cmd for cmd in link.sent)
    assert all(not cmd.startswith("{G") for cmd in link.sent)


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

    assert len(link.sent) == 2
    assert link.sent[0].startswith("{G0001#000P1100T0050!")
    assert "#031P0000T0000!" in link.sent[0]
    assert link.sent[1].startswith("{G0002#000P0900T0050!")
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


def test_cancelled_progress_callback_does_not_mutate_replacement_session() -> None:
    link = RecordingLink()
    runner = SequenceRunner(link)
    initial_groups = [
        ActionGroup(0, [(0, 1500, 50)]),
        ActionGroup(1, [(0, 1400, 50)]),
    ]
    replacement_groups = [
        ActionGroup(2, [(0, 1300, 50)]),
        ActionGroup(3, [(0, 1200, 50)]),
    ]
    finished: list[str] = []
    cancelled = False

    def cancel_initial_session(_current: int, _total: int) -> None:
        nonlocal cancelled
        if not cancelled:
            cancelled = True
            runner.cancel()

    def start_replacement(mode: str) -> None:
        finished.append(mode)
        if mode == "cancelled":
            runner.download(replacement_groups, 0, inter_frame_ms=1000)

    runner.progress.connect(cancel_initial_session)
    runner.finished.connect(start_replacement)

    runner.run_online(initial_groups, 0, 1, 1)

    assert runner._timer.interval() == 1000
    wait_until(lambda: finished == ["cancelled", "download"], timeout=1.5)
    assert link.sent[0] == "{#000P1500T0050!}"
    assert link.sent[1].startswith("{G0002#000P1300T0050!")
    assert link.sent[2].startswith("{G0003#000P1200T0050!")
    assert len(link.sent) == 3


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

    assert len(link.sent) == 1
    assert link.sent[0].startswith("{G0000#000P1500T0050!")
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
