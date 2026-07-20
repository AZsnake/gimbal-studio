from __future__ import annotations

import threading
from typing import Any

import serial
from PySide6.QtCore import QObject, Signal
from serial.tools import list_ports as serial_list_ports


class SerialLinkError(RuntimeError):
    """Raised when a serial link operation cannot be completed."""


def list_ports() -> list[str]:
    """Return the device name of every available serial port."""
    return [port.device for port in serial_list_ports.comports()]


class SerialLink(QObject):
    received = Signal(str)
    connection_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._serial: Any | None = None
        self._reader: threading.Thread | None = None
        self._stop_reader = threading.Event()
        self._state_lock = threading.Lock()
        self._write_lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        with self._state_lock:
            connection = self._serial
            return connection is not None and bool(connection.is_open)

    def connect(self, port: str, baud: int = 115200) -> None:
        self.disconnect()
        try:
            connection = serial.Serial(port, baudrate=baud, timeout=0.05)
        except (OSError, ValueError, serial.SerialException) as exc:
            message = str(exc)
            self.error_occurred.emit(message)
            raise SerialLinkError(message) from exc

        self._attach(connection)

    def attach_for_test(self, connection: Any) -> None:
        """Attach a serial-compatible object without opening a real port."""
        self.disconnect()
        self._attach(connection)

    def disconnect(self) -> None:
        with self._state_lock:
            connection = self._serial
            reader = self._reader
            self._serial = None
            self._reader = None
            self._stop_reader.set()

        if connection is None:
            return

        try:
            connection.close()
        except (OSError, serial.SerialException) as exc:
            self.error_occurred.emit(str(exc))

        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=1)
        self.connection_changed.emit(False)

    def send_text(self, data: str) -> None:
        with self._state_lock:
            connection = self._serial
            connected = connection is not None and bool(connection.is_open)
        if not connected:
            raise SerialLinkError("Serial port is not connected")

        try:
            with self._write_lock:
                connection.write(data.encode("utf-8"))
        except (OSError, serial.SerialException) as exc:
            message = str(exc)
            self.error_occurred.emit(message)
            raise SerialLinkError(message) from exc

    def _attach(self, connection: Any) -> None:
        if not bool(connection.is_open):
            raise SerialLinkError("Serial port is not open")

        with self._state_lock:
            self._serial = connection
            self._stop_reader.clear()
            self._reader = threading.Thread(
                target=self._read_loop,
                args=(connection,),
                name="SerialLinkReader",
                daemon=True,
            )
            reader = self._reader

        reader.start()
        self.connection_changed.emit(True)

    def _read_loop(self, connection: Any) -> None:
        while not self._stop_reader.is_set():
            try:
                data = connection.read(1024)
            except (OSError, serial.SerialException) as exc:
                if not self._stop_reader.is_set():
                    self.error_occurred.emit(str(exc))
                    self._disconnect_from_reader(connection)
                return

            if data:
                self.received.emit(data.decode("utf-8", errors="replace"))

    def _disconnect_from_reader(self, connection: Any) -> None:
        with self._state_lock:
            if self._serial is not connection:
                return
            self._serial = None
            self._reader = None
            self._stop_reader.set()

        try:
            connection.close()
        except (OSError, serial.SerialException):
            pass
        self.connection_changed.emit(False)
