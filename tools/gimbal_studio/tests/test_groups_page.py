from collections.abc import Iterator

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject
from PySide6.QtWidgets import QApplication

from gimbal_studio.project.models import ActionGroup, Project
from gimbal_studio.ui.groups_page import GroupsPage


APP = QApplication.instance() or QApplication([])


class RecordingLink(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[str] = []

    def send_text(self, command: str) -> None:
        self.sent.append(command)


@pytest.fixture
def groups_page() -> Iterator[tuple[GroupsPage, RecordingLink]]:
    link = RecordingLink()
    page = GroupsPage(link)
    yield page, link
    page.close()
    page.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    APP.processEvents()


def make_project() -> Project:
    return Project(
        groups=[
            ActionGroup(0, [(0, 1500, 1000), (1, 1500, 1000)]),
            ActionGroup(1, [(0, 1100, 800), (1, 1700, 800)]),
        ]
    )


def test_click_applies_pose_and_double_click_sends_group(groups_page) -> None:
    page, link = groups_page
    project = make_project()
    selected: list[list[tuple[int, int, int]]] = []
    page.pose_requested.connect(selected.append)
    page.set_project(project)

    page.table.cellClicked.emit(1, 0)
    page.table.cellDoubleClicked.emit(1, 0)

    assert selected == [[(0, 1100, 800), (1, 1700, 800)]]
    assert link.sent == ["{#000P1100T0800!#001P1700T0800!}"]


def test_edit_buttons_mutate_project_and_refresh_table(groups_page) -> None:
    page, _link = groups_page
    project = make_project()
    page.set_project(project)
    page.set_current_pose({0: 1250, 1: 1750}, 600)

    page.table.selectRow(0)
    page.insert_button.click()
    assert project.groups[0].moves == [(0, 1250, 600), (1, 1750, 600)]

    page.table.selectRow(1)
    page.copy_button.click()
    page.table.selectRow(2)
    page.paste_button.click()
    assert project.groups[2].moves == project.groups[1].moves
    assert project.groups[2] is not project.groups[1]

    page.table.selectRow(1)
    page.delete_button.click()

    assert [group.index for group in project.groups] == [0, 1]
    assert page.table.rowCount() == 2


def test_sequence_and_boot_buttons_dispatch_expected_commands(
    groups_page, monkeypatch
) -> None:
    page, link = groups_page
    project = make_project()
    page.set_project(project)
    calls: list[tuple] = []
    monkeypatch.setattr(
        page.runner,
        "run_online",
        lambda groups, start, end, count: calls.append(
            ("online", groups, start, end, count)
        ),
    )
    monkeypatch.setattr(
        page.runner,
        "run_offline",
        lambda start, end, count: calls.append(("offline", start, end, count)),
    )
    monkeypatch.setattr(
        page.runner,
        "download",
        lambda groups, start: calls.append(("download", groups, start)),
    )
    monkeypatch.setattr(page.runner, "cancel", lambda: calls.append(("cancel",)))
    page.start_spin.setValue(0)
    page.end_spin.setValue(1)
    page.count_spin.setValue(3)

    page.online_button.click()
    page.offline_button.click()
    page.download_button.click()
    page.set_boot_button.click()
    page.clear_boot_button.click()
    page.cancel_button.click()

    assert calls == [
        ("online", project.groups, 0, 1, 3),
        ("offline", 0, 1, 3),
        ("download", project.groups, 0),
        ("cancel",),
    ]
    assert link.sent == ["$PTL:0-1,3!", "$PTC!"]
