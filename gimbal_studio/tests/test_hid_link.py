import time

from gimbal_studio.transport.hid_link import (
    HidLink,
    decode_protocol_text,
    extract_payload,
    pack_reports,
)


class FakeHidDevice:
    def __init__(self, fail_times: int = 0):
        self.written: list[bytes] = []
        self.closed = False
        self._fails_left = fail_times

    def write(self, data: bytes) -> int:
        if self._fails_left > 0:
            self._fails_left -= 1
            return -1
        self.written.append(bytes(data))
        return len(data)

    def read(self, size: int, timeout_ms: int = 0):
        return []

    def set_nonblocking(self, _enabled: bool) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    def error(self) -> str:
        return "hid_write/WaitForSingleObject: (0x000003E5) Overlapped I/O operation is in progress."


def test_pack_reports_zide_matches_frida_capture():
    """Captured Zide $DRS! prefix: 02 02 0a 00 00 00 00 01 24 44 52 53 21"""
    report = pack_reports(b"$DRS!")[0]
    assert report[:13] == bytes.fromhex("02020a00000000012444525321")
    assert extract_payload(report) == b"$DRS!"


def test_pack_reports_zide_default_move():
    payload = b"#000P1500T1000!"
    report = pack_reports(payload)[0]
    assert report[0] == 2
    assert report[1] == 2
    assert report[2] == len(payload) + 5
    assert report[7] == 1
    assert report[8 : 8 + len(payload)] == payload
    assert extract_payload(report) == payload


def test_pack_reports_length_end():
    payload = b"#000P1500T1000!"
    report = pack_reports(payload, framing="length_end")[0]
    assert report[0] == 2
    assert report[1 : 1 + len(payload)] == payload
    assert report[63] == len(payload)
    assert extract_payload(report, framing="length_end") == payload


def test_pack_reports_length_prefix():
    payload = b"#000P1500T1000!"
    report = pack_reports(payload, framing="length_prefix")[0]
    assert report[0] == 2
    assert report[1] == len(payload)
    assert report[2 : 2 + len(payload)] == payload
    assert extract_payload(report, framing="length_prefix") == payload


def test_decode_protocol_text_ignores_binary_noise():
    assert decode_protocol_text(b"\x02\x1b\x00\xff") == []
    assert decode_protocol_text(b"noise#000P1500T1000!tail") == ["#000P1500T1000!"]


def test_hid_link_sends_zide_framing_and_retries():
    link = HidLink(enable_reader=False)
    fake = FakeHidDevice(fail_times=2)
    link.attach_for_test(fake)

    link.send_text("#000P1500T1000!")

    assert len(fake.written) == 1
    assert fake.written[0][:8] == bytes.fromhex("0202140000000001")
    assert fake.written[0][8:23] == b"#000P1500T1000!"
    assert link.is_connected
    assert link._reader is None

    link.disconnect()
    assert fake.closed


def test_hid_link_write_failure_keeps_connection():
    link = HidLink(enable_reader=False)
    fake = FakeHidDevice(fail_times=10)
    errors: list[str] = []
    link.error_occurred.connect(errors.append)
    link.attach_for_test(fake)

    try:
        link.send_text("#000P1500T1000!")
        raised = False
    except Exception:
        raised = True

    assert raised
    assert link.is_connected
    assert errors
    link.disconnect()


def test_hid_link_paces_multi_report_writes():
    """Long frames must space Interrupt OUT reports to avoid 0x000003E5."""
    link = HidLink(enable_reader=False)
    link._min_write_interval_s = 0.02
    fake = FakeHidDevice()
    link.attach_for_test(fake)

    # 80 bytes -> at least 2 reports with 56-byte zide ASCII capacity.
    payload = "{" + ("A" * 78) + "}"
    assert len(payload) > 56
    t0 = time.monotonic()
    link.send_text(payload)
    elapsed = time.monotonic() - t0

    assert len(fake.written) >= 2
    assert elapsed >= link._min_write_interval_s * (len(fake.written) - 1) * 0.8
    link.disconnect()
