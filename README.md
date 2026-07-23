# Gimbal Studio

面向 **ZL-IS2 云台／舵机控制器** 的跨平台图形上位机：串口与 HID 连接、PWM 云台控制、动作组编辑与执行、工程 INI 读写，以及通信日志。

应用代码位于 `gimbal_studio/`（PySide6 · Python 3.11+）。

> 本仓库为开源上位机参考实现。厂商手册、原理图与未公开硬件资料不随仓库分发（见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)）。

许可证：[MIT](LICENSE)（第三方与本地资料说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)）

---

## 功能亮点

| 方向 | 内容 |
|------|------|
| 连接 | 串口 115200 8N1，或免驱 HID（STM32 Custom HID） |
| 控制 | 二维盘 / 滑条 PWM 控制，急停 |
| 工程 | 打开／保存 `config_bes.ini` 风格工程，保留未知 INI 段 |
| 动作组 | 在线编辑、执行、下载到控制板；开机动作指令 |
| 打包 | PyInstaller one-folder 可执行文件（`scripts/pack.py`） |

---

## 仓库结构

```
gimbal-studio/
├── gimbal_studio/          # PySide6 应用（源码、测试、打包脚本）
│   ├── src/gimbal_studio/
│   ├── tests/
│   ├── scripts/            # pack.py 等
│   ├── pyproject.toml
│   └── README.md           # 安装、运行、验收清单
├── docs/                   # 设计规格等（厂商资料见 .gitignore）
├── LICENSE
├── THIRD_PARTY_NOTICES.md
└── README.md
```

---

## 快速上手

安装、运行、测试与打包步骤见 [`gimbal_studio/README.md`](gimbal_studio/README.md)。

摘要：

```bash
cd gimbal_studio
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m gimbal_studio
```
