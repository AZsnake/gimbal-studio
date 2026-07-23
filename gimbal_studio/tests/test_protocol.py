from gimbal_studio.protocol.commands import (
    build_move, build_multi, build_dgt, build_dgs, build_stop, build_reset,
    build_set_boot, build_clear_boot,
)
from gimbal_studio.protocol.parse import parse_group_body, format_group_line

def test_build_move_zero_pads():
    assert build_move(0, 1500, 1000) == "#000P1500T1000!"
    assert build_move(1, 650, 2000) == "#001P0650T2000!"

def test_build_multi_braces():
    s = build_multi([(0, 1500, 1000), (1, 1500, 1000)])
    assert s == "{#000P1500T1000!#001P1500T1000!}"

def test_dgt_dgs_stop():
    assert build_dgs(0) == "$DGS:0!"
    assert build_dgt(0, 10, 1) == "$DGT:0-10,1!"
    assert build_dgt(0, 4, 0) == "$DGT:0-4,0!"
    assert build_stop() == "$DST!"
    assert build_stop(3) == "$DST:3!"
    assert build_reset() == "$RST!"

def test_boot_commands():
    # Zide stores boot as angle-bracketed DGT; clear is empty <$!>
    assert build_set_boot(0, 5, 1) == "<$DGT:0-5,1!>"
    assert build_clear_boot() == "<$!>"

def test_parse_and_format_roundtrip():
    body = "#000P1500T1000!#001P1100T1800!"
    moves = parse_group_body(body)
    assert moves == [(0, 1500, 1000), (1, 1100, 1800)]
    line = format_group_line(2, moves, total_slots=4)
    assert line.startswith("G0002={G0002")
    assert "#000P1500T1000!" in line
    assert "#003P0000T0000!" in line  # 补齐未用槽
