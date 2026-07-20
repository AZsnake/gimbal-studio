# Gimbal Studio HID 扩展设计（2026-07-20）

**状态：** 已获对话确认（待你复核全文后进入实现计划）  
**位置：** `tools/gimbal_studio/`  

---

## 1. 背景

你当前设备在 Windows 上表现为 **HID**（`STM32 Custm HID`，`VID=0x0483`、`PID=0x5750`），而不是可枚举的 `COMx` 串口设备。现有 `gimbal_studio` 首版仅串口，导致无法连接。

本设计文档用于在不改变上层指令协议（仍发送 ZL-IS2/Zide 的 ASCII 指令）的前提下，新增 HID 传输能力，并与串口并存。

---

## 2. 目标与成功标准

### 2.1 目标（本次实现范围）

1. UI 顶部端口下拉混显：`HID: STM32 Custm HID` 与 `COMx`（并允许手动输入 `COMx`）。
2. 选择 HID 时：按与串口一致的方式发送文本协议（例如 `#000P1500T1000!`），并将设备回显写入日志页。
3. 选择串口时：保持现有行为（115200 8N1，串口可枚举/可手输）。

### 2.2 成功标准

在你的设备上：

- 下拉框能出现 `STM32 Custm HID`
- 选择 HID 并点击连接后，日志页能看到收发内容（至少发送成功、出现回显/响应）
- 控制页拖动二维盘能驱动物体动作

---

## 3. 总体架构（扩展点）

现有分层为：

`ui → project / serial_io / protocol`

本扩展建议在实现层做最小侵入式重构：

1. 由 UI 侧引入“连接方式”的选择逻辑（从选中项推导 transport 类型：串口或 HID）。
2. 在传输层实现统一的 API：
   - `connect(...) / disconnect()`
   - `send_text(cmd: str)`
   - `received(text: str)`、`connection_changed(bool)`、`error_occurred(str)`
3. UI/Protocol/Project 保持使用文本指令，不需要理解 HID report 结构。

---

## 4. 设备枚举与 UI 行为

### 4.1 设备枚举

- HID 枚举：通过 hidapi 枚举设备，默认过滤 `VID=0x0483`、`PID=0x5750`（后续可扩展）。
- 串口枚举：继续使用 `pyserial` 的 `list_ports` 返回 `COMx`。

合并后的下拉项示例：

- `HID: STM32 Custm HID (0483:5750) [path=...]`
- `COM11 (USB-SERIAL CH340)`

内部同时保存：

- 下拉显示字符串
- connect 所需的“连接标识”（HID 的 path 或唯一序号；串口的 COM 名称）

### 4.2 连接规则

- `HID:` 开头/内部标识为 HID → 走 HID transport（波特率控件禁用或不使用）
- `COM` → 走串口 transport（波特率控件生效）
- 扫不到 COM 时：仍支持手动输入 `COMx`（避免“空列表时按钮被禁用”的体验问题）

---

## 5. HID report 承载与解析（由 Zide 抓包驱动）

HID 层只负责把“文本协议”承载为 report payload，并从 report 里恢复文本。

### 5.1 抓包需要确认的参数

请在 Zide 正常连接设备后抓取至少一轮发送/接收，确认：

- report 长度（例如 64 字节）
- report ID（存在则记录；若 report ID 由系统固定可省略）
- payload 区偏移（payload 在 report 内从第几字节开始）
- 单个 report 可承载的最大 payload 长度
- 发送与接收是否使用同一种 report 方向（通常不同端口/不同 endpoint）

### 5.2 发送（send_text）

1. 将 `cmd` 按 UTF-8（或按抓包确认编码）转为字节序列。
2. 按抓包确认的 report 布局，将字节序列写入 payload 区域：
   - padding：不足则用 0x00 填充
   - 分片：超过 payload 容量时拆为多个 report（每个 report 保证 payload 起始偏移一致）
3. 调用 `hid_write(...)` 发送 report。

### 5.3 接收与文本恢复

1. 单独线程里循环读取 `hid_read(...)`。
2. 对每个 report：
   - 取出 payload 区字节
   - 以流方式拼接到缓冲区
3. 协议层文本恢复使用“终止符分割”策略：
   - 以协议终止字符 `!` 为消息边界（例如 `#...!...`）
   - 每当缓冲区出现 `!`，就截取出一条消息并 emit `received(text)`

> 若抓包发现设备并不以 `!` 作为边界，而是带长度字段/固定长度报文，则仅更新 HID transport 的解析参数与消息边界规则；protocol 层 API 不变。

---

## 6. 错误处理

- HID 设备权限/占用：
  - 连接或写入失败 → 通过 `error_occurred` 记录并弹窗提示“请关闭占用程序（如 Zide）或检查权限”
- 读线程异常：
  - 设备拔出/断开 → 断开连接并发 `connection_changed(False)`
- 非法数据：
  - report 里无法解码为文本时使用 `errors="replace"`，保证 UI 不崩溃

---

## 7. 测试策略（不依赖真实硬件）

### 7.1 HID 传输单元测试

实现一个 Fake HID backend：

- 输入：由测试构造的 report bytes 序列
- 输出：断言 `received(text)` 触发内容与分片/拼包行为符合预期

测试用例：

- 单 report 携带完整 `#...!` → 一次 emit
- 多 report 分片拼接后在 `!` 处 emit
- 非法字节 → emit 为 replace 解码后的文本（不抛异常）

### 7.2 UI 选择逻辑测试

- 枚举返回“仅 HID / HID+COM / 仅 COM”的组合
- 选择 HID 时：波特率控件禁用或不影响 connect 参数
- 选择 COM 时：波特率控件影响 connect 参数

---

## 8. 风险与对策

1. **最大风险：report framing 不一致**  
   对策：默认实现保持“参数化 framing”，后续只需更新 payload offset / report id / terminator 解析规则即可。
2. 跨平台差异  
   对策：本次先确保 Windows HID 路径；Linux/macOS 在后续阶段以相同接口补齐。
3. 设备占用  
   对策：连接失败时提示关闭 Zide；同时 UI 提供明确错误日志。

---

## 9. 本扩展与原规格的关系

原规格中“首版不做 HID 连接”的内容，与本次你选择的功能方向冲突。**以本扩展设计文档为准**：本次需要在首版实现 HID 传输能力（至少覆盖你当前的 `VID/PID` 设备）。

---

## 10. 下一步

当你复核并确认本文没有需要改动的地方后，我会继续进入实现计划（writing-plans），把工作拆成可落地的分步任务。

