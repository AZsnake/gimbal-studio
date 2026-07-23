import threading
import time

from gimbal_studio.transport.hid_link import HidLink
from gimbal_studio.transport.router import TransportRouter


class _FakeSerial:
    def __init__(self) -> None:
        self.is_open = True
        self.closed = False

    def close(self) -> None:
        self.is_open = False
        self.closed = True

    def write(self, data: bytes) -> int:
        return len(data)

    def read(self, size: int = 1) -> bytes:
        return b""


def test_router_disconnect_emits_connection_changed_false() -> None:
    """UI listens to router; detach-before-emit must not swallow disconnect."""
    from gimbal_studio.serial_io.port import SerialLink

    router = TransportRouter()
    events: list[bool] = []
    router.connection_changed.connect(events.append)

    link = SerialLink(router)
    router._active = link
    router._attach_active_signals(link)
    link.attach_for_test(_FakeSerial())
    assert events[-1] is True

    router.disconnect()

    assert router.is_connected is False
    assert events[-1] is False


def test_hid_disconnect_does_not_deadlock_when_reader_holds_io_lock() -> None:
    """Disconnect must not wait on io_lock held by a blocked HID read."""

    class BlockingReadDevice:
        def __init__(self) -> None:
            self.closed = False
            self._entered = threading.Event()
            self._release = threading.Event()

        def write(self, data: bytes) -> int:
            return len(data)

        def read(self, size: int, timeout_ms: int = 0):
            del size, timeout_ms
            self._entered.set()
            self._release.wait(timeout=2.0)
            return []

        def set_nonblocking(self, _enabled: bool) -> None:
            return None

        def close(self) -> None:
            self.closed = True
            self._release.set()

        def error(self) -> str:
            return ""

    link = HidLink(enable_reader=True)
    device = BlockingReadDevice()
    # Bypass connect probe; attach starts reader which grabs io_lock in read.
    link._attach(device)
    assert device._entered.wait(timeout=1.0)

    done = threading.Event()

    def disconnect_call() -> None:
        link.disconnect()
        done.set()

    worker = threading.Thread(target=disconnect_call, daemon=True)
    worker.start()
    finished = done.wait(timeout=1.0)
    worker.join(timeout=0.1)

    assert finished, "disconnect deadlocked waiting for reader io_lock"
    assert device.closed
    assert not link.is_connected
