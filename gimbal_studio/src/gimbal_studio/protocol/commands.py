def _id3(n: int) -> str:
    if not 0 <= n <= 254:
        raise ValueError(f"servo id out of range: {n}")
    return f"{n:03d}"


def _pwm4(n: int) -> str:
    if not 0 <= n <= 9999:
        raise ValueError(f"pwm out of range: {n}")
    return f"{n:04d}"


def _t4(n: int) -> str:
    if not 0 <= n <= 9999:
        raise ValueError(f"time out of range: {n}")
    return f"{n:04d}"


def build_move(servo_id: int, pwm: int, time_ms: int) -> str:
    return f"#{_id3(servo_id)}P{_pwm4(pwm)}T{_t4(time_ms)}!"


def build_multi(moves: list[tuple[int, int, int]]) -> str:
    return "{" + "".join(build_move(i, p, t) for i, p, t in moves) + "}"


def build_dgs(index: int) -> str:
    return f"$DGS:{index}!"


def build_dgt(start: int, end: int, count: int) -> str:
    return f"$DGT:{start}-{end},{count}!"


def build_stop(servo_id: int | None = None) -> str:
    return "$DST!" if servo_id is None else f"$DST:{servo_id}!"


def build_reset() -> str:
    return "$RST!"


def build_set_boot(start: int, end: int, count: int) -> str:
    # Zide "设为开机动作": store offline-run command for next power-on.
    return f"<$DGT:{start}-{end},{count}!>"


def build_clear_boot() -> str:
    # Zide "取消开机动作": clear the stored boot command string.
    return "<$!>"
