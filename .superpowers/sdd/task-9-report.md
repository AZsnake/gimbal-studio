# Task 9 Report
- 未连接或意外断线时禁用在线、脱机与下载按钮，并取消正在运行的序列。
- 串口连接失败会恢复断开状态，并通过 `QMessageBox` 显示具体错误。
- PWM 控件范围统一钳位到安全区间 500–2500。
- 写串口失败会关闭连接并发出 `connection_changed(False)`，主窗口同步刷新。
- 保留并验证方向键对前两轴进行 ±10 PWM 微调，含子控件聚焦场景。
- 新增连接状态、失败提示、PWM 钳位和写失败断线回归测试。
- 已将本任务触及的 Python 文件统一为 LF。
- 验证：`python -m pytest -q` → `49 passed`，退出码 0。
- 未实施 Task 10+，未推送远端。

## Task 9 Review Fixes

- **连接态按钮归属**：`GroupsPage._update_run_buttons()` 不再启用在线/脱机/下载；`refresh()` 发出 `actions_need_update`，由 `MainWindow._update_sequence_actions()` 统一根据连接态、组数与范围启用。
- **测试**：新增 `test_add_group_while_disconnected_keeps_sequence_actions_disabled`；`python -m pytest -q` → **50 passed**。
- **Commit**：`fix(gimbal-studio): 断线时编辑动作组不启用执行按钮` → **（见下方 SHA）**。
