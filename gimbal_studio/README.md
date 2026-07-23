# Gimbal Studio

Gimbal Studio 是面向 ZL-IS2 云台／舵机控制器的跨平台图形工具，支持
串口与 HID 连接、PWM 云台控制、动作组编辑与执行、工程 INI 读写、下载和通信日志。

## 环境要求

- Python 3.11 或更高版本
- Windows、Linux 或 macOS
- 串口波特率默认：115200（HID 连接不使用波特率）

运行依赖为 PySide6、pyserial 和 hidapi；测试与打包还需要 pytest 和 PyInstaller。

## 安装

在本目录 `gimbal_studio` 下创建虚拟环境并安装：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Linux／macOS 使用：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

只运行应用、不测试或打包时，可将最后一条命令改为
`python -m pip install -e .`。

## 运行

激活虚拟环境后执行：

```bash
python -m gimbal_studio
```

也可以执行安装生成的 `gimbal-studio` 命令。连接控制板前，在窗口中选择正确
设备：

- `HID: STM32 Custm HID`（本机常见免驱 HID 连接）
- 或 `COMx`（串口，按 115200 波特率）

若设备管理器只有 HID、没有 COM，请选择 HID 项连接。连接前请先关闭 Zide，避免占用。

## 打开 config_bes.ini

1. 启动应用，选择“文件 → 打开”。
2. 打开仓库中的
   `docs/路舵机控制器资料/003-软件工具/001-图形化上位机软件/config_bes.ini`。
3. 检查水平通道（ID 0）、倾斜通道（ID 1）以及动作组 G0000–G0019。

保存前建议备份原文件。应用会保留不能编辑的未知 INI 段，但第一次连接真机时
仍建议使用副本验收。

## Linux 串口权限

多数 Linux 发行版要求当前用户属于 `dialout` 组：

```bash
sudo usermod -aG dialout "$USER"
```

执行后注销并重新登录，再用 `groups` 确认权限。如果发行版使用其他串口组
（例如 `uucp`），请加入该发行版对应的组。

## 开机动作指令

当前协议常量位于 `src/gimbal_studio/protocol/commands.py`（对照 Zide V5.99 字符串表）：

- 设置开机动作：`<$DGT:<起始组>-<结束组>,<次数>!>`（尖括号表示存为开机命令；脱机运行仍用无尖括号的 `$DGT:...!`）
- 取消开机动作：`<$!>`

## 测试

```bash
python -m pytest -q
```

自动化测试不连接硬件；串口和运动行为需按下方清单手动验收。

## PyInstaller 打包

先安装开发依赖，再在本目录运行：

```bash
python scripts/pack.py
```

脚本使用当前 Python 环境生成 one-folder、无控制台窗口的应用，输出目录为
`dist/GimbalStudio/`。PyInstaller 会通过 `--collect-data gimbal_studio` 收集
包内资源（含 `resources/theme.qss`），避免 frozen 应用启动时找不到主题。
打包产物与操作系统相关，应分别在目标平台打包；Windows 入口通常为
`dist/GimbalStudio/GimbalStudio.exe`。

## 手动验收清单

- [ ] 能枚举串口并以 115200 波特率连接。
- [ ] 拖动控制页二维盘和滑条时云台响应，急停有效。
- [ ] 能打开 `config_bes.ini`，通道和动作组显示正确。
- [ ] 能在线执行一段扫描动作组。
- [ ] 下载后能用 `$DGT` 脱机执行；若控制板支持存储，断电重启后仍可执行。
- [ ] 日志页能正确显示收发的原始指令。
- [ ] Windows 与至少另一平台源码可运行，且打包脚本能在主开发平台生成可执行文件。
