# Gimbal Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `tools/gimbal_studio/` 实现开源跨平台 PySide6 云台上位机，串口控制 ZL-IS2，兼容 Zide `.ini`，覆盖实时控制、动作组在线/脱机/下载与急停。

**Architecture:** 分层单体：`protocol`（纯指令）→ `serial_io`（收发）/ `project`（工程模型）→ `ui`（标签页）。依赖单向，协议与 ini 无硬件可测。

**Tech Stack:** Python 3.11+、PySide6、pyserial、pytest、PyInstaller（打包脚本）

**Spec:** `docs/superpowers/specs/2026-07-20-gimbal-studio-design.md`

## Global Constraints

- 仅串口，默认波特率 **115200**，8N1；不做 HID
- UI：**PySide6**；布局三标签（控制 / 动作组 / 串口日志）；主题 **石墨琥珀**
- 通道：仅渲染 `.ini` 中 `enable=true`；二维盘绑定前两个启用通道
- 兼容打开 `config_bes.ini`；未知 ini 段 **原样保留**
- 首版不做：手柄/红外/映射/IO/固件升级
- 提交说明：中文 Conventional Commits（`feat|fix|test|docs|chore(scope): …`）
- 工作目录：仓库根下 `tools/gimbal_studio/`

## File Structure

| 路径 | 职责 |
|------|------|
| `tools/gimbal_studio/pyproject.toml` | 包元数据与依赖 |
| `tools/gimbal_studio/README.md` | 安装、运行、串口权限、打包 |
| `tools/gimbal_studio/LICENSE` | MIT |
| `tools/gimbal_studio/src/gimbal_studio/__init__.py` | 版本号 |
| `tools/gimbal_studio/src/gimbal_studio/__main__.py` | `python -m gimbal_studio` |
| `tools/gimbal_studio/src/gimbal_studio/app.py` | QApplication 启动 |
| `tools/gimbal_studio/src/gimbal_studio/protocol/commands.py` | 指令构建 |
| `tools/gimbal_studio/src/gimbal_studio/protocol/parse.py` | 组负载解析 |
| `tools/gimbal_studio/src/gimbal_studio/serial_io/port.py` | 枚举/连接/读写线程 |
| `tools/gimbal_studio/src/gimbal_studio/project/models.py` | SteerChannel、ActionGroup、Project |
| `tools/gimbal_studio/src/gimbal_studio/project/ini_io.py` | 读/写 Zide ini |
| `tools/gimbal_studio/src/gimbal_studio/ui/theme.qss` | 石墨琥珀样式 |
| `tools/gimbal_studio/src/gimbal_studio/ui/main_window.py` | 主窗+顶栏+标签 |
| `tools/gimbal_studio/src/gimbal_studio/ui/control_page.py` | 二维盘+滑条 |
| `tools/gimbal_studio/src/gimbal_studio/ui/pad_widget.py` | 二维盘控件 |
| `tools/gimbal_studio/src/gimbal_studio/ui/groups_page.py` | 动作组页 |
| `tools/gimbal_studio/src/gimbal_studio/ui/log_page.py` | 串口日志 |
| `tools/gimbal_studio/src/gimbal_studio/ui/runner.py` | 在线执行/下载会话（可取消） |
| `tools/gimbal_studio/scripts/pack.py` | PyInstaller 包装 |
| `tools/gimbal_studio/tests/fixtures/minimal_bes.ini` | 精简夹具 |
| `tools/gimbal_studio/tests/test_protocol.py` | 协议测试 |
| `tools/gimbal_studio/tests/test_ini_io.py` | 工程 I/O 测试 |
| `tools/gimbal_studio/tests/test_serial_io.py` | 串口层（假串口） |
| `tools/gimbal_studio/tests/test_runner.py` | 在线执行调度 |

---

### Task 1: 脚手架与可安装包

**Files:**
- Create: `tools/gimbal_studio/pyproject.toml`
- Create: `tools/gimbal_studio/LICENSE`
- Create: `tools/gimbal_studio/src/gimbal_studio/__init__.py`
- Create: `tools/gimbal_studio/src/gimbal_studio/__main__.py`
- Create: `tools/gimbal_studio/src/gimbal_studio/app.py`
- Create: `tools/gimbal_studio/tests/test_smoke_import.py`

**Interfaces:**
- Consumes: 无
- Produces: 包名 `gimbal_studio`；`__version__ = "0.1.0"`；入口 `python -m gimbal_studio` 可启动空窗（后续任务填满）

- [ ] **Step 1: 写失败的冒烟测试**

```python
# tests/test_smoke_import.py
def test_version_defined():
    import gimbal_studio
    assert gimbal_studio.__version__ == "0.1.0"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd tools/gimbal_studio && pip install -e ".[dev]" && pytest tests/test_smoke_import.py -v`  
Expected: FAIL（包不存在或无版本）

- [ ] **Step 3: 最小脚手架**

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "gimbal-studio"
version = "0.1.0"
description = "Cross-platform serial GUI for ZL-IS2 gimbal / servo controller"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = [
  "PySide6>=6.6",
  "pyserial>=3.5",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pyinstaller>=6.0"]

[project.scripts]
gimbal-studio = "gimbal_studio.app:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

```python
# src/gimbal_studio/__init__.py
__version__ = "0.1.0"
```

```python
# src/gimbal_studio/app.py
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
import sys

def main() -> int:
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("Gimbal Studio")
    win.setCentralWidget(QLabel("Gimbal Studio — scaffolding"))
    win.resize(960, 640)
    win.show()
    return app.exec()

# src/gimbal_studio/__main__.py
from gimbal_studio.app import main
raise SystemExit(main())
```

`LICENSE`：标准 MIT 全文，Copyright 写项目年份 2026。

先放占位 `README.md`（一行：`# Gimbal Studio`），Task 10 再写完整。

- [ ] **Step 4: 测试通过**

Run: `cd tools/gimbal_studio && pip install -e ".[dev]" && pytest tests/test_smoke_import.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/gimbal_studio
git commit -m "chore(gimbal-studio): 初始化可安装包脚手架"
```

---

### Task 2: 协议编解码

**Files:**
- Create: `tools/gimbal_studio/src/gimbal_studio/protocol/__init__.py`
- Create: `tools/gimbal_studio/src/gimbal_studio/protocol/commands.py`
- Create: `tools/gimbal_studio/src/gimbal_studio/protocol/parse.py`
- Create: `tools/gimbal_studio/tests/test_protocol.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `build_move(servo_id: int, pwm: int, time_ms: int) -> str`
  - `build_multi(moves: list[tuple[int, int, int]]) -> str`  # → `{#000P…!#001P…!}`
  - `build_dgs(index: int) -> str`
  - `build_dgt(start: int, end: int, count: int) -> str`
  - `build_stop(servo_id: int | None = None) -> str`
  - `build_reset() -> str`
  - `build_set_boot(start: int, end: int, count: int) -> str`  # `$PTL:s-e,c!`，真机可改常量
  - `build_clear_boot() -> str`  # `$PTC!`
  - `parse_group_body(body: str) -> list[tuple[int, int, int]]`  # 从 `#000P1500T1000!…` 解析
  - `format_group_line(index: int, moves: list[tuple[int, int, int]], total_slots: int = 32) -> str`  # 写回 `G0000={G0000#000P…!…}` 内层

- [ ] **Step 1: 写失败测试**

```python
# tests/test_protocol.py
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
    assert build_set_boot(0, 5, 1) == "$PTL:0-5,1!"
    assert build_clear_boot() == "$PTC!"

def test_parse_and_format_roundtrip():
    body = "#000P1500T1000!#001P1100T1800!"
    moves = parse_group_body(body)
    assert moves == [(0, 1500, 1000), (1, 1100, 1800)]
    line = format_group_line(2, moves, total_slots=4)
    assert line.startswith("G0002={G0002")
    assert "#000P1500T1000!" in line
    assert "#003P0000T0000!" in line  # 补齐未用槽
```

- [ ] **Step 2: 运行确认失败**

Run: `cd tools/gimbal_studio && pytest tests/test_protocol.py -v`  
Expected: FAIL import / 未定义

- [ ] **Step 3: 实现**

```python
# protocol/commands.py
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
    # 若真机不符，只改此处字符串模板
    return f"$PTL:{start}-{end},{count}!"

def build_clear_boot() -> str:
    return "$PTC!"
```

```python
# protocol/parse.py
import re
from gimbal_studio.protocol.commands import build_move

_MOVE_RE = re.compile(r"#(\d{3})P(\d{4})T(\d{4})!")

def parse_group_body(body: str) -> list[tuple[int, int, int]]:
    return [(int(a), int(b), int(c)) for a, b, c in _MOVE_RE.findall(body)]

def format_group_line(index: int, moves: list[tuple[int, int, int]], total_slots: int = 32) -> str:
    by_id = {i: (p, t) for i, p, t in moves}
    parts = []
    for slot in range(total_slots):
        p, t = by_id.get(slot, (0, 0))
        parts.append(build_move(slot, p, t))
    tag = f"G{index:04d}"
    inner = tag + "".join(parts)
    return f"{tag}={{{inner}}}"
```

```python
# protocol/__init__.py
from gimbal_studio.protocol.commands import *
from gimbal_studio.protocol.parse import parse_group_body, format_group_line
```

- [ ] **Step 4: 测试通过**

Run: `pytest tests/test_protocol.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/gimbal_studio/src/gimbal_studio/protocol tools/gimbal_studio/tests/test_protocol.py
git commit -m "feat(gimbal-studio): 实现舵机串口指令编解码"
```

---

### Task 3: 工程模型与 Zide ini 读写

**Files:**
- Create: `tools/gimbal_studio/src/gimbal_studio/project/models.py`
- Create: `tools/gimbal_studio/src/gimbal_studio/project/ini_io.py`
- Create: `tools/gimbal_studio/src/gimbal_studio/project/__init__.py`
- Create: `tools/gimbal_studio/tests/fixtures/minimal_bes.ini`
- Create: `tools/gimbal_studio/tests/test_ini_io.py`

**Interfaces:**
- Consumes: `parse_group_body`, `format_group_line`, `build_multi`
- Produces:
  - `@dataclass SteerChannel`: title, id, bias, pmin, pmax, lab_left, lab_right, enable, x, y
  - `@dataclass ActionGroup`: index: int, moves: list[tuple[int,int,int]]
  - `@dataclass Project`: steers: list[SteerChannel], groups: list[ActionGroup], raw_sections: dict[str, list[tuple[str,str]]], meta: dict
  - `enabled_steers(project) -> list[SteerChannel]`
  - `load_ini(path: Path) -> Project`
  - `save_ini(project: Project, path: Path) -> None`
  - `group_command(group: ActionGroup) -> str`  # `build_multi` 仅含有意义通道或全量 moves

- [ ] **Step 1: 写夹具 `tests/fixtures/minimal_bes.ini`**

从 `config_bes.ini` 精简：`[global]`、`[group]` 含 G0000–G0001、`[steer0]`/`[steer1]` enable=true、一个 `[steer2]` enable=false、保留一个空 `[LD0]` 作为未知段样例。内容手写对齐 Zide 格式（`G0000={G0000#000P1500T1000!#001P1500T1000!...}` 至少写满 0–1，其余槽 `P0000T0000` 可只写到 `#003` 以缩短，但 `total_slots` 读写要与实现一致——**夹具与 `format_group_line(..., 32)` 一致时用 32 槽**；为可读性夹具可用 4 槽并让 loader 接受可变长度）。

约定：**loader 按实际出现的 `#NNN` 解析；saver 对启用通道 + 组内出现过的 id 写回，缺省槽补 `#iiiP0000T0000!`，默认 `total_slots=32`。** 夹具可用完整两行短组：

```ini
[global]
zide_version=Zide V5.99
timeDownload=300
bg_index=0

[group]
GROUP={ NUM ------S00------------S01------ }
G0000={G0000#000P1500T1000!#001P1500T1000!}
G0001={G0001#000P1100T1800!#001P1500T1800!}

[steer0]
title=水平
id=0
x=200
y=350
bias=0
pmin=500
pmax=2500
labLeft=左
labRight=右
enable=true

[steer1]
title=倾斜
id=1
x=200
y=200
bias=0
pmin=500
pmax=2500
labLeft=仰
labRight=俯
enable=true

[steer2]
title=S2
id=2
x=0
y=0
bias=0
pmin=500
pmax=2500
labLeft=小
labRight=大
enable=false

[LD0]
ldName=未命名
ldCmd=
```

- [ ] **Step 2: 写失败测试**

```python
from pathlib import Path
from gimbal_studio.project.ini_io import load_ini, save_ini
from gimbal_studio.project.models import enabled_steers

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_bes.ini"

def test_load_enabled_and_groups():
    p = load_ini(FIXTURE)
    en = enabled_steers(p)
    assert [s.title for s in en] == ["水平", "倾斜"]
    assert en[0].id == 0 and en[0].pmin == 500
    assert len(p.groups) == 2
    assert p.groups[0].moves[0] == (0, 1500, 1000)

def test_roundtrip_preserves_unknown_section(tmp_path):
    p = load_ini(FIXTURE)
    out = tmp_path / "out.ini"
    save_ini(p, out)
    text = out.read_text(encoding="utf-8")
    assert "[LD0]" in text
    assert "ldName=未命名" in text
    p2 = load_ini(out)
    assert enabled_steers(p2)[0].title == "水平"
    assert p2.groups[1].moves[0] == (0, 1100, 1800)
```

- [ ] **Step 3: 运行确认失败**

Run: `pytest tests/test_ini_io.py -v`  
Expected: FAIL

- [ ] **Step 4: 实现 models + ini_io**

实现要点：
- 用 `configparser` 时注意：Zide 的 `G0000={...}` 含特殊字符；若 configparser 捣乱，改用手写分段解析（推荐）：按行扫描 `[section]`，节内 `key=value`；`[group]` 下 `G\d+` 用 `parse_group_body`。
- `raw_sections`：非 `global`/`group`/`steer*`/`cellName`/`cellCount` 的节整节保存为有序列表，`save_ini` 原样写回。
- `steer*`：`enable` 解析 `true`/`false` 大小写不敏感。

- [ ] **Step 5: 测试通过后，另加真实文件冒烟（可选）**

若仓库存在 `docs/**/config_bes.ini`，增加：

```python
def test_load_real_bes_if_present():
    candidates = list(Path(__file__).resolve().parents[3].joinpath("docs").rglob("config_bes.ini"))
    if not candidates:
        return
    p = load_ini(candidates[0])
    assert len(enabled_steers(p)) >= 2
    assert len(p.groups) >= 1
```

Run: `pytest tests/test_ini_io.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/gimbal_studio/src/gimbal_studio/project tools/gimbal_studio/tests/test_ini_io.py tools/gimbal_studio/tests/fixtures
git commit -m "feat(gimbal-studio): 实现 Zide 兼容工程 ini 读写"
```

---

### Task 4: 串口收发层

**Files:**
- Create: `tools/gimbal_studio/src/gimbal_studio/serial_io/__init__.py`
- Create: `tools/gimbal_studio/src/gimbal_studio/serial_io/port.py`
- Create: `tools/gimbal_studio/tests/test_serial_io.py`

**Interfaces:**
- Consumes: 无（只发字符串）
- Produces: 类 `SerialLink(QObject)`：
  - `list_ports() -> list[str]`（静态或模块函数）
  - `connect(port: str, baud: int = 115200) -> None`（失败抛 `SerialLinkError`）
  - `disconnect() -> None`
  - `is_connected: bool`
  - `send_text(data: str) -> None`（未连接抛错；内部编码 UTF-8 / ASCII）
  - 信号：`received(str)`、`connection_changed(bool)`、`error_occurred(str)`
  - 读循环：后台 `QThread` 或 `threading.Thread` + 信号；写串行锁

- [ ] **Step 1: 写失败测试（假串口）**

```python
import threading, time
from gimbal_studio.serial_io.port import SerialLink, list_ports, SerialLinkError

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
    def push(self, s: str):
        with self.lock:
            self._read_buf += s.encode("ascii", errors="ignore")

def test_send_and_receive(qtbot=None):
    # 无 pytest-qt 时用直连回调列表
    link = SerialLink()
    fake = FakeSerial()
    link.attach_for_test(fake)
    got = []
    link.received.connect(got.append)
    link.send_text("#000P1500T1000!")
    assert fake.written[-1] == b"#000P1500T1000!"
    fake.push("OK\n")
    # 等读线程
    deadline = time.time() + 2
    while not got and time.time() < deadline:
        time.sleep(0.05)
        from PySide6.QtCore import QCoreApplication
        app = QCoreApplication.instance()
        if app:
            app.processEvents()
    assert any("OK" in g for g in got)
    link.disconnect()

def test_send_when_disconnected_raises():
    link = SerialLink()
    try:
        link.send_text("x")
        assert False
    except SerialLinkError:
        pass
```

若无 QApplication，测试文件顶部：

```python
import sys
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_serial_io.py -v`  
Expected: FAIL

- [ ] **Step 3: 实现 `SerialLink`**

要点：`attach_for_test` 仅测试用；生产路径 `serial.Serial(port, baudrate, timeout=0.05)`。`list_ports` 用 `serial.tools.list_ports.comports()` 返回 `device` 列表。

- [ ] **Step 4: 测试通过**

Run: `pytest tests/test_serial_io.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/gimbal_studio/src/gimbal_studio/serial_io tools/gimbal_studio/tests/test_serial_io.py
git commit -m "feat(gimbal-studio): 实现串口连接与收发线程"
```

---

### Task 5: 在线执行 / 下载 Runner

**Files:**
- Create: `tools/gimbal_studio/src/gimbal_studio/ui/runner.py`
- Create: `tools/gimbal_studio/tests/test_runner.py`

**Interfaces:**
- Consumes: `SerialLink.send_text`、`build_multi` / `group_command`、`build_dgt`、`ActionGroup`
- Produces: 类 `SequenceRunner(QObject)`：
  - `run_online(groups: list[ActionGroup], start: int, end: int, count: int) -> None`
  - `run_offline(start: int, end: int, count: int) -> None`  # 发一条 `$DGT`
  - `download(groups: list[ActionGroup], from_index: int, inter_frame_ms: int = 300) -> None`
  - `cancel() -> None`
  - 信号：`progress(int, int)`、`finished(str)`、`failed(str)`
  - **下载策略（可真机替换）：** 对 `groups[from_index:]` 依次 `send_text(group_command(g))`，帧间 `inter_frame_ms`（来自 ini `timeDownload`）；注释标明若与 Zide 抓包不符，仅改 `download()` 内发送内容

- [ ] **Step 1: 写失败测试**

```python
from gimbal_studio.project.models import ActionGroup
from gimbal_studio.ui.runner import SequenceRunner

class RecLink:
    def __init__(self):
        self.sent = []
    def send_text(self, s: str):
        self.sent.append(s)

def test_offline_sends_dgt():
    link = RecLink()
    r = SequenceRunner(link)
    r.run_offline(0, 4, 1)
    assert link.sent == ["$DGT:0-4,1!"]

def test_online_sends_each_group_once():
    link = RecLink()
    r = SequenceRunner(link)
    groups = [
        ActionGroup(0, [(0, 1500, 50), (1, 1500, 50)]),
        ActionGroup(1, [(0, 1100, 50), (1, 1500, 50)]),
    ]
    # 同步模式：测试可用 run_online_blocking 或极短 time + processEvents
    r.run_online_blocking(groups, 0, 1, 1)
    assert len(link.sent) == 2
    assert link.sent[0].startswith("{#000P1500T0050!")
```

实现时可提供 `run_online_blocking` 专供测试；UI 用异步 `QTimer`/`QThread`。

- [ ] **Step 2–4: 失败 → 实现 → 通过**（同上模式）

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(gimbal-studio): 实现动作组在线执行与下载会话"
```

---

### Task 6: 主窗壳、主题、顶栏连接

**Files:**
- Create: `tools/gimbal_studio/src/gimbal_studio/resources/theme.qss`
- Create: `tools/gimbal_studio/src/gimbal_studio/ui/main_window.py`
- Create: `tools/gimbal_studio/src/gimbal_studio/ui/log_page.py`
- Modify: `tools/gimbal_studio/src/gimbal_studio/app.py`

**Interfaces:**
- Consumes: `SerialLink`, `list_ports`
- Produces: `MainWindow` 含 `SerialLink` 实例、三标签占位、顶栏品牌「Gimbal Studio」、端口/波特率/连接；日志页绑定 `received`/`send`

- [ ] **Step 1: 实现 `theme.qss`（石墨琥珀）**

CSS 变量式注释 + 实际 QSS：背景 `#141414`/`#1e1e1e`，文字 `#f3f3f0`，强调 `#e8a54b`，危险急停偏红。无紫色渐变。

- [ ] **Step 2: `LogPage`** — `QPlainTextEdit` 收/发、发送按钮、清空；`submit_command(str)` 信号

- [ ] **Step 3: `MainWindow`**

```python
# 结构要点
# menubar 可选：打开/保存工程（Task 8 接）
# toolbar/top: QLabel("Gimbal Studio"), QComboBox ports, refresh, baud, connect btn, status dot
# QTabWidget: 控制 | 动作组 | 串口日志
```

`app.py` 加载 QSS、创建 `MainWindow`。

- [ ] **Step 4: 手工启动**

Run: `python -m gimbal_studio`  
Expected: 深色窗、三标签、可刷新 COM 列表（无板也可）

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(gimbal-studio): 添加主窗壳与石墨琥珀主题"
```

---

### Task 7: 控制页（二维盘 + 滑条）

**Files:**
- Create: `tools/gimbal_studio/src/gimbal_studio/ui/pad_widget.py`
- Create: `tools/gimbal_studio/src/gimbal_studio/ui/control_page.py`
- Modify: `tools/gimbal_studio/src/gimbal_studio/ui/main_window.py`

**Interfaces:**
- Consumes: `Project`/`enabled_steers`、`SerialLink.send_text`、`build_move`、`build_stop`
- Produces: `ControlPage.set_project(project)`；`pose_changed(dict[int,int])`；节流发送（例如 ≥30ms）；归中 1500；方向键 ±10 PWM

- [ ] **Step 1: `PadWidget`**

`QWidget` 绘制圆盘；鼠标拖动发 `value_changed(nx: float, ny: float)`，范围 -1..1；映射到两通道 `pmin..pmax`。

- [ ] **Step 2: `ControlPage`**

左 Pad，右动态滑条；`QSpinBox` 同步；`Time` 共用；未连接不发送但可改 UI。

- [ ] **Step 3: 接入 MainWindow 默认空 Project（两通道演示）或启动时尝试加载 fixture**

- [ ] **Step 4: 真机手测（有板时）** — 拖动水平/倾斜、急停

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(gimbal-studio): 实现云台控制页与二维盘"
```

---

### Task 8: 动作组页 + 工程打开保存

**Files:**
- Create: `tools/gimbal_studio/src/gimbal_studio/ui/groups_page.py`
- Modify: `main_window.py`（文件对话框、共享 Project）

**Interfaces:**
- Consumes: `load_ini`/`save_ini`、`SequenceRunner`、`ControlPage` 同步姿态
- Produces: 表格增删插、复制粘贴、双击下发、在线/脱机/下载/开机；打开 `config_bes.ini`

- [ ] **Step 1: 实现 `GroupsPage` 表格与编辑操作**（改 `Project.groups` 后刷新）

- [ ] **Step 2: 接线 SequenceRunner 按钮与取消**

- [ ] **Step 3: 单击组 → `ControlPage.apply_pose(moves)`；双击 → `send_text(group_command)`**

- [ ] **Step 4: 手测打开 `docs/**/config_bes.ini`，在线跑 G0000–G0003**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(gimbal-studio): 实现动作组编辑与工程文件开关"
```

---

### Task 9: 错误处理打磨 + 键盘微调

**Files:**
- Modify: `control_page.py`, `main_window.py`, `port.py`

- [ ] **Step 1: 断开时禁用执行/下载；连接失败 `QMessageBox`；PWM 钳位**
- [ ] **Step 2: 控制页 `keyPressEvent` 方向键调整前两轴**
- [ ] **Step 3: 意外断线 `connection_changed(False)` 刷新 UI**
- [ ] **Step 4: `pytest` 全绿**
- [ ] **Step 5: Commit**

```bash
git commit -m "fix(gimbal-studio): 完善断线提示与键盘微调"
```

---

### Task 10: README 与 PyInstaller 打包脚本

**Files:**
- Modify: `tools/gimbal_studio/README.md`
- Create: `tools/gimbal_studio/scripts/pack.py`

**Interfaces:**
- Produces: 文档含安装、`python -m gimbal_studio`、Linux `dialout`、开机指令常量说明、打包命令

- [ ] **Step 1: 写 README**（中英可只中文）：依赖、运行、打开 `config_bes.ini`、验收清单摘自规格 §7.2

- [ ] **Step 2: `scripts/pack.py`**

```python
"""Build one-folder app with PyInstaller."""
import subprocess, sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
subprocess.check_call([
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--windowed", "--name", "GimbalStudio",
    "--paths", str(root / "src"),
    str(root / "src" / "gimbal_studio" / "__main__.py"),
])
```

- [ ] **Step 3: 在开发机试跑打包（允许耗时）**

Run: `cd tools/gimbal_studio && python scripts/pack.py`  
Expected: `dist/GimbalStudio/` 可启动

- [ ] **Step 4: Commit**

```bash
git add tools/gimbal_studio/README.md tools/gimbal_studio/scripts/pack.py
git commit -m "docs(gimbal-studio): 补充 README 与打包脚本"
```

- [ ] **Step 5: 真机验收勾选规格 §7.2**；若 `$PTL`/`$PTC` 或下载帧不符，只改 `protocol/commands.py` / `runner.download` 并补测试后另提交 `fix(gimbal-studio): 校正开机/下载指令`

---

## Spec Coverage Self-Review

| 规格项 | 任务 |
|--------|------|
| 串口连接 115200 | T4, T6 |
| 二维盘+滑条、enable 通道 | T7, T3 |
| 标签三页 + 石墨琥珀 | T6–T8 |
| ini 兼容 / 未知段保留 | T3 |
| 在线 / 脱机 `$DGT` / 下载 / 急停 | T2, T5, T8 |
| 开机设/取消 | T2, T8, T10 真机校正 |
| 串口日志 | T6 |
| 方向键 | T9 |
| 错误处理 | T4, T9 |
| 单元测试 protocol/project | T2, T3 |
| PyInstaller + README | T10 |
| 非目标（HID/外设/固件） | 全局约束，无任务实现 |

**占位符扫描：** 下载与 `$PTL`/`$PTC` 允许真机改常量，已限定修改点，无笼统 TBD。

**类型一致性：** `ActionGroup(index, moves)`、`build_move`/`build_multi`/`SerialLink.send_text` 贯穿 T2–T8。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-20-gimbal-studio.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 每任务新开子代理，任务间复查，迭代快  
2. **Inline Execution** — 本会话用 executing-plans 按检查点批量执行  

Which approach?
