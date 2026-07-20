import threading
import time

import pytest
from PySide6.QtCore import QCoreApplication

from gimbal_studio.serial_io.port import SerialLink, SerialLinkError, list_ports


APP = QCoreApplication.instance() or QCoreApplication([])


class FakeSerial:
    def __init__(self):
        self.is_open = True
        self.written = []
        self._read_buf = b""
        self.timeout = 0.05
        self.lock = threading.Lock()

    def write(self, data: bytes):
        self.written.append(data)
        return len(data)

    def read(self, n: int = 1) -> bytes:
        time.sleep(0.01)
        with self.lock:
            if not self._read_buf:
                return b""
            out, self._read_buf = self._read_buf[:n], self._read_buf[n:]
            return out

    def close(self):
        self.is_open = False

    def push(self, data: str):
        with self.lock:
            self._read_buf += data.encode("ascii", errors="ignore")


def test_send_and_receive():
    link = SerialLink()
    fake = FakeSerial()
    link.attach_for_test(fake)
    received = []
    link.received.connect(received.append)

    link.send_text("#000P1500T1000!")

    assert fake.written[-1] == b"#000P1500T1000!"
    fake.push("OK\n")
    deadline = time.time() + 2
    while not received and time.time() < deadline:
        time.sleep(0.05)
        APP.processEvents()

    assert any("OK" in message for message in received)
    link.disconnect()
    assert not link.is_connected
    assert not fake.is_open


def test_send_when_disconnected_raises():
    link = SerialLink()

    with pytest.raises(SerialLinkError):
        link.send_text("x")


def test_list_ports_returns_device_names(monkeypatch):
    class Port:
        def __init__(self, device):
            self.device = device

    monkeypatch.setattr(
        "serial.tools.list_ports.comports",
        lambda: [Port("COM3"), Port("COM7")],
    )

    assert list_ports() == ["COM3", "COM7"]


def test_connection_changes_are_emitted():
    link = SerialLink()
    states = []
    link.connection_changed.connect(states.append)

    link.attach_for_test(FakeSerial())
    link.disconnect()

    assert states == [True, False]


def test_connect_wraps_open_failures(monkeypatch):
    def fail_to_open(*args, **kwargs):
        raise ValueError("invalid port")

    monkeypatch.setattr("gimbal_studio.serial_io.port.serial.Serial", fail_to_open)
    link = SerialLink()
    errors = []
    link.error_occurred.connect(errors.append)

    with pytest.raises(SerialLinkError, match="invalid port"):
        link.connect("bad-port")

    assert errors == ["invalid port"]
