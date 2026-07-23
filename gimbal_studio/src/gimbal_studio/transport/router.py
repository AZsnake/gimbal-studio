from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import QObject, Signal

from gimbal_studio.serial_io.port import SerialLink, SerialLinkError
from gimbal_studio.transport.errors import TransportError
from gimbal_studio.transport.hid_link import HidLink, list_hid_devices


class TransportRouter(QObject):
    """Routes UI text commands to either SerialLink or HidLink."""

    received = Signal(str)
    connection_changed = Signal(bool)
    error_occurred = Signal(str)
    sent = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._active: SerialLink | HidLink | None = None

    @property
    def is_connected(self) -> bool:
        return bool(self._active and self._active.is_connected)

    @staticmethod
    def enumerate_devices() -> tuple[list[str], list[dict[str, Any]]]:
        """Return (serial_ports, hid_devices)."""
        serial_ports: list[str] = []
        try:
            from gimbal_studio.serial_io.port import list_ports

            serial_ports = list_ports()
        except Exception:
            serial_ports = []

        vid = int(os.getenv("GIMBAL_HID_VID", "0x0483"), 16)
        pid = int(os.getenv("GIMBAL_HID_PID", "0x5750"), 16)
        hid_devices = list_hid_devices(vid=vid, pid=pid)
        return serial_ports, hid_devices

    def _attach_active_signals(self, active: Any) -> None:
        active.received.connect(self.received.emit)
        active.connection_changed.connect(self.connection_changed.emit)
        active.error_occurred.connect(self.error_occurred.emit)

    def _detach_active_signals(self, active: Any) -> None:
        for signal, slot in (
            (active.received, self.received.emit),
            (active.connection_changed, self.connection_changed.emit),
            (active.error_occurred, self.error_occurred.emit),
        ):
            try:
                signal.disconnect(slot)
            except Exception:
                pass

    def disconnect(self) -> None:
        active = self._active
        if not active:
            return
        # Detach first so active.disconnect()'s own emit is not double-forwarded,
        # then emit on the router so MainWindow always leaves the connected UI.
        self._detach_active_signals(active)
        self._active = None
        try:
            active.disconnect()
        finally:
            self.connection_changed.emit(False)

    def connect(self, port: str, baud: int = 115200) -> None:
        self.disconnect()
        active = SerialLink(self)
        self._active = active
        self._attach_active_signals(active)
        try:
            active.connect(port, baud)
        except SerialLinkError as exc:
            self._detach_active_signals(active)
            self._active = None
            raise TransportError(str(exc)) from exc

    def connect_hid(self, path: Any) -> None:
        self.disconnect()
        # Write-only HID: interrupt OUT only. Background read caused false errors
        # and SetOutputReport never reached firmware DataOut handler.
        # Reader on: Zide framing yields HID IN ACKs / board text.
        active = HidLink(self, enable_reader=True)
        self._active = active
        self._attach_active_signals(active)
        try:
            active.connect(path)
        except TransportError:
            self._detach_active_signals(active)
            self._active = None
            raise

    def send_text(self, data: str) -> None:
        if not self._active:
            raise TransportError("Not connected")
        try:
            self._active.send_text(data)
        except SerialLinkError as exc:
            raise TransportError(str(exc)) from exc
        self.sent.emit(data)
