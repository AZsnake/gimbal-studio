from __future__ import annotations

import glob
import os
import re
import select
import threading
import time
from typing import Any

from PySide6.QtCore import QObject, Signal

from gimbal_studio.transport.errors import TransportError

# Observed board: STM32 Custm HID (VID_0483 / PID_5750).
DEFAULT_VID = 0x0483
DEFAULT_PID = 0x5750

# Zide V5.99 hid_write framing (Frida capture, 2026-07-22):
#   [ReportID=2][0x02][len=payload+5][00 00 00 00][0x01][ASCII...]
# ASCII starts at offset 8. length_prefix/length_end do NOT move the board.
DEFAULT_REPORT_SIZE = 64
DEFAULT_REPORT_ID = 2
DEFAULT_LENGTH_OFFSET = 2
DEFAULT_PAYLOAD_OFFSET = 8
DEFAULT_MAX_PAYLOAD_LEN = 56
DEFAULT_FRAMING = "zide"
ZIDE_HEADER_PAD = 5  # bytes[3:8] counted inside length field

_PROTOCOL_MESSAGE = re.compile(rb"[#${][^#${]*?!")


def _import_hid() -> Any:
    try:
        import hid  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise TransportError(
            "缺少 hid 依赖。请安装: pip install hidapi"
        ) from exc
    return hid


def _linux_hidraw_paths(vid: int, pid: int) -> list[bytes]:
    """Map VID/PID to /dev/hidrawN via sysfs (libusb-backed hidapi paths are unusable)."""
    if os.name == "nt":
        return []
    needle = f"HID_ID=0003:{vid:08X}:{pid:08X}".upper()
    found: list[bytes] = []
    for uevent_path in glob.glob("/sys/class/hidraw/hidraw*/device/uevent"):
        try:
            text = open(uevent_path, encoding="utf-8", errors="replace").read().upper()
        except OSError:
            continue
        if needle not in text:
            continue
        name = uevent_path.split("/device/")[0].rsplit("/", 1)[-1]
        node = f"/dev/{name}"
        if os.path.exists(node):
            found.append(node.encode("ascii"))
    return found


class _HidrawDevice:
    """Minimal hidapi-like wrapper over Linux /dev/hidraw*."""

    def __init__(self, path: bytes) -> None:
        path_text = path.decode("utf-8", errors="replace")
        self._fd = os.open(path_text, os.O_RDWR)
        self._nonblocking = False
        self._last_error = ""

    def write(self, data: bytes) -> int:
        try:
            return os.write(self._fd, data)
        except OSError as exc:
            self._last_error = str(exc)
            return -1

    def read(self, size: int, timeout_ms: int = 0) -> list[int]:
        if self._nonblocking or timeout_ms == 0:
            try:
                ready, _, _ = select.select([self._fd], [], [], 0)
                if not ready:
                    return []
            except (OSError, ValueError):
                return []
        elif timeout_ms > 0:
            try:
                ready, _, _ = select.select([self._fd], [], [], timeout_ms / 1000.0)
                if not ready:
                    return []
            except (OSError, ValueError):
                return []
        try:
            data = os.read(self._fd, size)
        except OSError as exc:
            self._last_error = str(exc)
            return []
        return list(data)

    def set_nonblocking(self, enabled: bool) -> None:
        self._nonblocking = bool(enabled)

    def close(self) -> None:
        try:
            os.close(self._fd)
        except OSError:
            pass

    def error(self) -> str:
        return self._last_error


def list_hid_devices(
    vid: int = DEFAULT_VID,
    pid: int = DEFAULT_PID,
) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    hidraw_paths = _linux_hidraw_paths(vid, pid)

    try:
        hid = _import_hid()
    except TransportError:
        hid = None

    try:
        infos: list[dict[str, Any]] = []
        if hid is not None:
            infos = list(hid.enumerate(vid, pid))
        if not infos and hidraw_paths:
            infos = [
                {
                    "path": p,
                    "product_string": "STM32 Custm HID",
                    "vendor_id": vid,
                    "product_id": pid,
                    "usage_page": 0,
                    "usage": 0,
                    "manufacturer_string": "",
                    "serial_number": "",
                }
                for p in hidraw_paths
            ]

        # Prefer concrete /dev/hidraw* paths on Linux when libusb paths are opaque.
        hidraw_iter = iter(hidraw_paths)

        for info in infos:
            usage_page = int(info.get("usage_page") or 0)
            # Windows reports vendor usage pages (>= 0xFF00). Linux hidapi often
            # returns usage_page=0 for the same device — do not drop those.
            if usage_page != 0 and usage_page < 0xFF00:
                continue
            product = (info.get("product_string") or "STM32 Custm HID").strip()
            path = info.get("path")
            if hidraw_paths:
                try:
                    path = next(hidraw_iter)
                except StopIteration:
                    path = hidraw_paths[0]
            if path is None:
                continue
            path_text = (
                path.decode("utf-8", errors="replace")
                if isinstance(path, (bytes, bytearray))
                else str(path)
            )
            display = f"HID: {product}"
            if any(d["display"] == display for d in devices):
                display = (
                    f"HID: {product} "
                    f"(usage {usage_page:04X}:{int(info.get('usage') or 0):02X})"
                )
            devices.append(
                {
                    "display": display,
                    "path": path,
                    "path_text": path_text,
                    "vendor_id": int(info.get("vendor_id") or vid),
                    "product_id": int(info.get("product_id") or pid),
                    "product_string": product,
                    "manufacturer_string": info.get("manufacturer_string") or "",
                    "serial_number": info.get("serial_number") or "",
                    "usage_page": usage_page,
                    "usage": int(info.get("usage") or 0),
                }
            )
    except Exception:
        return []
    return devices

def pack_reports(
    payload: bytes,
    *,
    report_size: int = DEFAULT_REPORT_SIZE,
    report_id: int = DEFAULT_REPORT_ID,
    framing: str = DEFAULT_FRAMING,
    length_offset: int = DEFAULT_LENGTH_OFFSET,
    payload_offset: int = DEFAULT_PAYLOAD_OFFSET,
    max_payload_len: int = DEFAULT_MAX_PAYLOAD_LEN,
) -> list[bytes]:
    """Pack ASCII into HID interrupt-OUT reports."""
    if report_size <= 0:
        raise TransportError("invalid report_size")

    if framing == "zide":
        # Frida: [id=2][0x02][len=ascii+5][00*4][0x01][ascii @ 8]
        payload_offset = 8
        length_offset = 2
        capacity = min(max_payload_len, report_size - payload_offset)
    elif framing == "raw":
        data_offset = 1
        capacity = min(max_payload_len, report_size - data_offset)
        length_offset = -1
        payload_offset = data_offset
    elif framing == "length_end":
        # [id][data 62 bytes][len at byte 63]
        data_offset = 1
        capacity = min(62, report_size - 2)
        length_offset = report_size - 1
        payload_offset = data_offset
    else:
        # length_prefix: [id][len][data...]
        length_offset = 1
        payload_offset = 2
        capacity = min(62, report_size - payload_offset)

    if capacity <= 0:
        raise TransportError("invalid max_payload_len")

    reports: list[bytes] = []
    offset = 0
    while offset < len(payload) or (offset == 0 and not payload):
        chunk = payload[offset : offset + capacity]
        report = bytearray(report_size)
        report[0] = report_id & 0xFF
        if framing == "zide":
            report[1] = 0x02
            report[2] = (len(chunk) + ZIDE_HEADER_PAD) & 0xFF
            report[3:7] = b"\x00\x00\x00\x00"
            report[7] = 0x01
            report[8 : 8 + len(chunk)] = chunk
        elif framing == "length_end":
            report[payload_offset : payload_offset + len(chunk)] = chunk
            report[length_offset] = len(chunk) & 0xFF
        elif length_offset >= 0:
            report[length_offset] = len(chunk) & 0xFF
            report[payload_offset : payload_offset + len(chunk)] = chunk
        else:
            report[payload_offset : payload_offset + len(chunk)] = chunk
        reports.append(bytes(report))
        offset += len(chunk)
        if not payload:
            break
    return reports


def extract_payload(
    report: bytes,
    *,
    report_id: int = DEFAULT_REPORT_ID,
    framing: str = DEFAULT_FRAMING,
    length_offset: int = DEFAULT_LENGTH_OFFSET,
    payload_offset: int = DEFAULT_PAYLOAD_OFFSET,
    max_payload_len: int = DEFAULT_MAX_PAYLOAD_LEN,
) -> bytes:
    if not report:
        return b""
    data = bytes(report)
    if data[0] != report_id:
        data = bytes([report_id]) + data

    if framing == "raw":
        return data[1:].rstrip(b"\x00")
    if framing == "length_end":
        length = data[-1]
        length = max(0, min(int(length), 62, len(data) - 2))
        return bytes(data[1 : 1 + length])
    if framing == "zide":
        if len(data) < 9:
            return b""
        total = int(data[2])
        ascii_len = max(0, total - ZIDE_HEADER_PAD)
        ascii_len = min(ascii_len, max_payload_len, len(data) - 8)
        return bytes(data[8 : 8 + ascii_len])

    # length_prefix
    length_offset = 1
    payload_offset = 2
    max_here = 62 if max_payload_len == DEFAULT_MAX_PAYLOAD_LEN else max_payload_len
    length = data[length_offset]
    start = payload_offset
    length = max(0, min(int(length), max_here, len(data) - start))
    return bytes(data[start : start + length])


def decode_protocol_text(payload: bytes) -> list[str]:
    if not payload:
        return []
    cleaned = bytes(b for b in payload if 32 <= b <= 126)
    return [m.group().decode("ascii") for m in _PROTOCOL_MESSAGE.finditer(cleaned)]


class HidLink(QObject):
    """HID transport using Interrupt OUT (hid_write). Write-only by default."""

    received = Signal(str)
    connection_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        report_size: int = DEFAULT_REPORT_SIZE,
        report_id: int = DEFAULT_REPORT_ID,
        enable_reader: bool = False,
    ) -> None:
        super().__init__(parent)
        self._device: Any | None = None
        self._reader: threading.Thread | None = None
        self._reader_stop: threading.Event | None = None
        self._state_lock = threading.Lock()
        self._io_lock = threading.Lock()
        self._rx_buffer = bytearray()
        self._enable_reader = enable_reader

        self.report_size = report_size
        self.report_id = report_id
        # Default "zide" matches commercial Zide V5.99 hid_write buffers.
        self.framing = DEFAULT_FRAMING
        # Zide paces HID with hidSendTimer; rapid multi-report bursts cause
        # Windows hidapi ERROR_IO_PENDING (0x000003E5) and stall the OUT pipe.
        self._write_retries = 5
        self._min_write_interval_s = 0.08
        self._last_write_mono = 0.0

    @property
    def is_connected(self) -> bool:
        with self._state_lock:
            return self._device is not None

    def connect(self, path: Any) -> None:
        self.disconnect()
        device: Any | None = None
        last_error = "HID open failed"
        path_bytes = (
            path
            if isinstance(path, (bytes, bytearray))
            else str(path).encode("utf-8", errors="replace")
        )

        # 1) Linux hidraw first — bundled hidapi is often libusb-backed and
        # cannot open without write access to /dev/bus/usb/...
        candidates: list[bytes] = []
        if path_bytes.startswith(b"/dev/hidraw"):
            candidates.append(bytes(path_bytes))
        candidates.extend(_linux_hidraw_paths(DEFAULT_VID, DEFAULT_PID))
        # de-dupe
        seen: set[bytes] = set()
        ordered: list[bytes] = []
        for item in candidates:
            if item not in seen:
                seen.add(item)
                ordered.append(item)

        for hidraw_path in ordered:
            try:
                device = _HidrawDevice(hidraw_path)
                break
            except OSError as exc:
                last_error = str(exc) or last_error

        # 2) Fall back to hidapi (Windows / systems with working backend).
        if device is None:
            try:
                hid = _import_hid()
                device = hid.device()
                device.open_path(path_bytes)
            except Exception as exc:
                last_error = str(exc) or last_error
                device = None

        if device is None:
            self.error_occurred.emit(last_error)
            raise TransportError(last_error)

        try:
            device.set_nonblocking(bool(self._enable_reader))
        except Exception:
            pass

        # Fail fast if OUT pipe is stalled / device held by another app.
        # Match Zide connect: uart_hid_send_str("$DRS!") — not $DST! (estop).
        try:
            probe = pack_reports(
                b"$DRS!",
                report_size=self.report_size,
                report_id=self.report_id,
                framing=self.framing,
            )[0]
            with self._io_lock:
                written = device.write(probe)
                self._last_write_mono = time.monotonic()
                if written is not None and written < 0:
                    detail = ""
                    try:
                        detail = device.error() or ""
                    except Exception:
                        detail = ""
                    raise OSError(self._format_write_error(written, detail))
        except Exception as exc:
            try:
                device.close()
            except Exception:
                pass
            message = str(exc) or "HID write probe failed"
            self.error_occurred.emit(message)
            raise TransportError(message) from exc

        self._attach(device)

    def attach_for_test(self, device: Any) -> None:
        self.disconnect()
        self._attach(device)

    def disconnect(self) -> None:
        with self._state_lock:
            device = self._device
        if device is not None:
            self._disconnect_device(device)

    def _disconnect_device(self, device: Any) -> None:
        with self._state_lock:
            if self._device is not device:
                return
            reader = self._reader
            reader_stop = self._reader_stop
            self._device = None
            self._reader = None
            self._reader_stop = None
            self._rx_buffer.clear()
            if reader_stop is not None:
                reader_stop.set()

        # Close without holding _io_lock: the reader may be blocked inside
        # device.read() while holding that lock; waiting here deadlocks UI.
        try:
            device.close()
        except Exception as exc:
            self.error_occurred.emit(str(exc))

        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=1)
        self.connection_changed.emit(False)

    def send_text(self, data: str) -> None:
        with self._state_lock:
            device = self._device
        if device is None:
            raise TransportError("HID device is not connected")

        payload = data.encode("ascii", errors="strict")
        reports = pack_reports(
            payload,
            report_size=self.report_size,
            report_id=self.report_id,
            framing=self.framing,
        )
        last_error: Exception | None = None
        for report in reports:
            for attempt in range(self._write_retries):
                try:
                    # Pace OUT pipe outside the device lock so the reader can run.
                    gap = self._min_write_interval_s - (
                        time.monotonic() - self._last_write_mono
                    )
                    if gap > 0:
                        time.sleep(gap)
                    with self._io_lock:
                        written = device.write(report)
                        self._last_write_mono = time.monotonic()
                        detail = ""
                        try:
                            detail = device.error() or ""
                        except Exception:
                            detail = ""
                    if written is not None and written < 0:
                        raise OSError(self._format_write_error(written, detail))
                    if written is not None and written < len(report):
                        raise OSError(
                            self._format_write_error(
                                written, detail or "short write"
                            )
                        )
                    break
                except Exception as exc:
                    last_error = exc
                    time.sleep(0.2 * (attempt + 1))
            else:
                message = str(last_error) if last_error else "HID write failed"
                self.error_occurred.emit(message)
                raise TransportError(message) from last_error

    @staticmethod
    def _format_write_error(rc: int, detail: str) -> str:
        tip = ""
        if "0x000003E5" in detail or "in progress" in detail.lower():
            tip = (
                "。通常是 HID 被占用或 USB 管道卡住："
                "请关闭 Zide / 其他 GimbalStudio，"
                "然后拔掉控制板 USB 再插上后重连"
            )
        detail_part = f", {detail}" if detail else ""
        return f"hid_write failed (rc={rc}{detail_part}){tip}"

    def _attach(self, device: Any) -> None:
        with self._state_lock:
            self._device = device
            if self._enable_reader:
                reader_stop = threading.Event()
                self._reader_stop = reader_stop
                self._reader = threading.Thread(
                    target=self._read_loop,
                    args=(device, reader_stop),
                    name="HidLinkReader",
                    daemon=True,
                )
                self._reader.start()
        self.connection_changed.emit(True)

    def _read_loop(self, device: Any, reader_stop: threading.Event) -> None:
        """Optional RX path — disabled by default for this board."""
        while not reader_stop.is_set():
            try:
                with self._io_lock:
                    data = device.read(self.report_size, timeout_ms=50)
            except TypeError:
                try:
                    with self._io_lock:
                        data = device.read(self.report_size)
                except Exception:
                    time.sleep(0.05)
                    continue
            except Exception:
                time.sleep(0.05)
                continue

            if not data:
                time.sleep(0.01)
                continue

            payload = extract_payload(bytes(data), framing=self.framing)
            if not payload:
                payload = extract_payload(bytes(data), framing="raw")
            if not payload:
                continue
            self._rx_buffer.extend(payload)
            cleaned = bytes(b for b in self._rx_buffer if 32 <= b <= 126)
            messages = decode_protocol_text(cleaned)
            if not messages:
                # Board often ACKs with non-protocol binary; still surface printable.
                if cleaned and self.framing == "zide":
                    text = cleaned.decode("ascii", errors="ignore").strip()
                    if text:
                        self.received.emit(text)
                    self._rx_buffer.clear()
                    continue
                self._rx_buffer.clear()
                self._rx_buffer.extend(cleaned[-128:])
                continue
            for message in messages:
                self.received.emit(message)
            last = messages[-1].encode("ascii")
            idx = cleaned.rfind(last)
            self._rx_buffer.clear()
            if idx >= 0:
                self._rx_buffer.extend(cleaned[idx + len(last) :])
