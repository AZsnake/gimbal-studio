# Design: STABLIZER 根目录元数据对齐

日期：2026-07-23

## 目标

按 MIPI / RF / S2C 兄弟仓的**根目录文档格式**整理本仓，不移动应用代码。

## 范围（方案 A + 轻量对齐）

新增：

- 根 `README.md`：项目简介、仓库结构、许可证；**无**「相关项目」表；安装运行细节指向 `gimbal_studio/README.md`
- 根 `LICENSE`：MIT，`Copyright (c) 2026 AZsnake`
- 根 `THIRD_PARTY_NOTICES.md`：厂商资料目录说明 + Python 依赖许可提示

同步：

- `gimbal_studio/LICENSE` 版权行改为 `AZsnake`
- `.gitignore` 保持现有规则，采用分段注释风格

不改：

- 不把 `gimbal_studio/` 迁回 `tools/`
- 不改应用源码与 `pyproject.toml` 行为

## 发布

远程仓库：[AZsnake/gimbal-studio](https://github.com/AZsnake/gimbal-studio)
