# Gimbal Studio 启动工程加载设计（2026-07-22）

**状态：** 已获对话确认  
**位置：** `tools/gimbal_studio/`  

---

## 1. 目标

启动时自动加载工程 INI，并记住上次打开路径；若无可用文件则在当前目录生成带展示动作序列的默认 `config.ini`。

### 成功标准

- 有有效 `last_project_path` → 加载该文件  
- 否则加载 `cwd/config.ini`；不存在则创建默认展示工程再加载  
- 打开/保存成功后更新记忆路径（`QSettings`）  
- 标题栏显示当前工程文件名  

---

## 2. 启动解析（优先级 B）

1. 读 `QSettings("STABLIZER", "GimbalStudio")` 键 `last_project_path`  
2. 路径非空且文件存在 → 用之  
3. 否则若 `Path.cwd() / "config.ini"` 存在 → 用之  
4. 否则写入默认工程到 `cwd/config.ini` 并用之  
5. 加载失败 → 日志错误；尽量回退创建/加载 cwd 默认；再失败则内存内置 `default_project()`（不写盘）

打开成功、保存/另存为成功 → 写入绝对路径到 `last_project_path`。

---

## 3. 默认展示工程

- 仅启用：水平 id=0、倾斜 id=1  
- 动作组 G0–G7：归中 → 左 → 右 → 归中 → 仰 → 俯 → 对角 → 归中  
  - 时间约 500–900 ms（见实现常量）  
- 通过 `default_project()` + `save_ini` 生成，不填充 32 路空舵机  

---

## 4. 模块

| 单元 | 职责 |
|------|------|
| `project/defaults.py` | `default_project()`、`ensure_default_config(path)` |
| `project/startup.py` | `resolve_startup_path(cwd, last_path)`、settings 读写 |
| `MainWindow` | 启动调用解析并 `load_ini`/`set_project`；打开/保存更新 settings |

不改协议；无首次向导；不在本特性中记忆窗口几何。

---

## 5. 测试

- `resolve_startup_path` 三种优先级  
- `default_project`：2 启用舵机、8 组、compact 无 `#031`  
- `ensure_default_config` 创建可加载文件  
- MainWindow：启动后 `current_path` 正确；打开后 last 更新  
