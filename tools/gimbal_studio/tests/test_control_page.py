from PySide6.QtCore import QObject, QPoint, Qt, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gimbal_studio.project.models import Project, SteerChannel
from gimbal_studio.ui.control_page import ControlPage
from gimbal_studio.ui.pad_widget import PadWidget


APP = QApplication.instance() or QApplication([])


class FakeSerialLink(QObject):
    connection_changed = Signal(bool)

    def __init__(self, connected: bool = False) -> None:
        super().__init__()
        self.is_connected = connected
        self.sent: list[str] = []

    def send_text(self, command: str) -> None:
        self.sent.append(command)

    def set_connected(self, connected: bool) -> None:
        self.is_connected = connected
        self.connection_changed.emit(connected)


def make_project() -> Project:
    return Project(
        steers=[
            SteerChannel(title="水平", id=0, pmin=500, pmax=2500, enable=True),
            SteerChannel(title="倾斜", id=1, pmin=700, pmax=2300, enable=True),
            SteerChannel(title="禁用", id=2, enable=False),
        ]
    )


def test_pad_emits_normalized_position() -> None:
    pad = PadWidget()
    pad.resize(240, 240)
    pad.show()
    values: list[tuple[float, float]] = []
    pad.value_changed.connect(lambda x, y: values.append((x, y)))

    QTest.mousePress(
        pad,
        Qt.MouseButton.LeftButton,
        pos=QPoint(pad.width() - 1, pad.height() // 2),
    )

    assert values[-1][0] > 0.95
    assert abs(values[-1][1]) < 0.05


def test_control_page_builds_enabled_channels_and_applies_pose() -> None:
    link = FakeSerialLink()
    page = ControlPage(link)
    changed: list[dict[int, int]] = []
    page.pose_changed.connect(changed.append)

    page.set_project(make_project())
    page.apply_pose([(0, 1200, 900), (1, 1800, 900), (2, 2000, 900)])

    assert set(page.sliders) == {0, 1}
    assert page.sliders[0].value() == 1200
    assert page.spin_boxes[1].value() == 1800
    assert page.time_spin.value() == 900
    assert changed[-1] == {0: 1200, 1: 1800}
    assert link.sent == []


def test_control_changes_emit_pose_and_send_only_while_connected() -> None:
    link = FakeSerialLink()
    page = ControlPage(link)
    page.set_project(make_project())
    changed: list[dict[int, int]] = []
    page.pose_changed.connect(changed.append)

    page.spin_boxes[0].setValue(1600)
    QTest.qWait(35)
    assert changed[-1][0] == 1600
    assert link.sent == []

    link.is_connected = True
    page.spin_boxes[0].setValue(1700)
    page.spin_boxes[0].setValue(1710)
    QTest.qWait(50)

    assert link.sent == ["#000P1710T1000!"]


def test_pad_center_stop_and_arrow_keys_control_pose() -> None:
    link = FakeSerialLink(connected=True)
    page = ControlPage(link)
    page.set_project(make_project())

    page.pad.value_changed.emit(1.0, -1.0)
    assert page.spin_boxes[0].value() == 2500
    assert page.spin_boxes[1].value() == 700

    page.center_button.click()
    assert page.current_pose() == {0: 1500, 1: 1500}

    QTest.keyClick(page, Qt.Key.Key_Right)
    QTest.keyClick(page, Qt.Key.Key_Up)
    assert page.current_pose() == {0: 1510, 1: 1510}

    page.stop_button.click()
    assert link.sent[-1] == "$DST!"


def test_emergency_stop_cancels_pending_moves() -> None:
    link = FakeSerialLink(connected=True)
    page = ControlPage(link)
    page.set_project(make_project())

    page.spin_boxes[0].setValue(1600)
    page.emergency_stop()
    QTest.qWait(40)

    assert link.sent == ["$DST!"]


def test_arrow_keys_control_pad_while_channel_widgets_have_focus() -> None:
    link = FakeSerialLink()
    page = ControlPage(link)
    page.set_project(make_project())
    page.show()
    page.activateWindow()
    assert QTest.qWaitForWindowActive(page)

    page.spin_boxes[0].setFocus()
    QTest.keyClick(page.spin_boxes[0], Qt.Key.Key_Right)
    assert page.current_pose() == {0: 1510, 1: 1500}

    page.sliders[1].setFocus()
    QTest.keyClick(page.sliders[1], Qt.Key.Key_Up)
    assert page.current_pose() == {0: 1510, 1: 1510}
    page.close()


def test_offline_edit_is_not_sent_after_quick_reconnect() -> None:
    link = FakeSerialLink()
    page = ControlPage(link)
    page.set_project(make_project())

    page.spin_boxes[0].setValue(1600)
    link.set_connected(True)
    QTest.qWait(40)

    assert link.sent == []


def test_disconnect_drops_moves_queued_while_connected() -> None:
    link = FakeSerialLink(connected=True)
    page = ControlPage(link)
    page.set_project(make_project())

    page.spin_boxes[0].setValue(1600)
    link.set_connected(False)
    link.set_connected(True)
    QTest.qWait(40)

    assert link.sent == []
