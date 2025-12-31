<div align="center">

# Claude Code Bridge (ccb) v2.3

**基于终端分屏的 Claude & Codex & Gemini 丝滑协作工具**

**打造真实的大模型专家协作团队，给 Claude Code / Codex / Gemini 配上"不会遗忘"的搭档**

<p>
  <img src="https://img.shields.io/badge/交互皆可见-096DD9?style=for-the-badge" alt="交互皆可见">
  <img src="https://img.shields.io/badge/模型皆可控-CF1322?style=for-the-badge" alt="模型皆可控">
</p>
<p>
  <img src="https://img.shields.io/badge/Every_Interaction_Visible-096DD9?style=for-the-badge" alt="Every Interaction Visible">
  <img src="https://img.shields.io/badge/Every_Model_Controllable-CF1322?style=for-the-badge" alt="Every Model Controllable">
</p>

[![Version](https://img.shields.io/badge/version-2.3-orange.svg)]()
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)]()

[English](README.md) | **中文**

<img src="assets/demo.webp" alt="双窗口协作演示" width="900">

</div>

---

**简介：** 多模型协作能够有效避免模型偏见、认知漏洞和上下文限制，然而 MCP、Skills 等直接调用 API 方式存在诸多局限性。本项目打造了一套新的方案。

## ⚡ 核心优势

| 特性 | 价值 |
| :--- | :--- |
| **🖥️ 可见可控** | 多模型分屏 CLI 挂载，所见即所得，完全掌控。 |
| **🧠 持久上下文** | 每个 AI 独立记忆，关闭后可随时恢复（`-r` 参数）。 |
| **📉 节省 Token** | 仅发送轻量级指令，而非整个代码库历史 (~20k tokens)。 |
| **🪟 原生终端体验** | 直接集成于 **WezTerm** (推荐) 或 tmux，无需配置复杂的服务器。 |

---

## 🚀 快速开始

**第一步：** 安装 [WezTerm](https://wezfurlong.org/wezterm/)（Windows 请安装原生 `.exe` 版本）

**第二步：** 根据你的环境选择安装脚本：

<details>
<summary><b>Linux</b></summary>

```bash
git clone https://github.com/bfly123/claude_code_bridge.git
cd claude_code_bridge
./install.sh install
```

</details>

<details>
<summary><b>macOS</b></summary>

```bash
git clone https://github.com/bfly123/claude_code_bridge.git
cd claude_code_bridge
./install.sh install
```

> **注意：** 如果安装后找不到命令，请参考 [macOS 故障排除](#-macos-安装指南)。

</details>

<details>
<summary><b>WSL (Windows 子系统)</b></summary>

> 如果你的 Claude/Codex/Gemini 运行在 WSL 中，请使用此方式。

> **⚠️ 警告：** 请勿使用 root/管理员权限安装或运行 ccb。请先切换到普通用户（`su - 用户名` 或使用 `adduser` 创建新用户）。

```bash
# 在 WSL 终端中运行（使用普通用户，不要用 root）
git clone https://github.com/bfly123/claude_code_bridge.git
cd claude_code_bridge
./install.sh install
```

</details>

<details>
<summary><b>Windows 原生</b></summary>

> 如果你的 Claude/Codex/Gemini 运行在 Windows 原生环境，请使用此方式。

```powershell
git clone https://github.com/bfly123/claude_code_bridge.git
cd claude_code_bridge
powershell -ExecutionPolicy Bypass -File .\install.ps1 install
```

</details>

### 启动
```bash
ccb up codex            # 启动 Codex
ccb up gemini           # 启动 Gemini
ccb up codex gemini     # 同时启动两个
```

### 常用参数
| 参数 | 说明 | 示例 |
| :--- | :--- | :--- |
| `-r` | 恢复上次会话上下文 | `ccb up codex -r` |
| `-a` | 全自动模式，跳过权限确认 | `ccb up codex -a` |
| `-h` | 查看详细帮助信息 | `ccb -h` |
| `-v` | 查看当前版本和检测更新 | `ccb -v` |

### 后续更新
```bash
ccb update              # 更新 ccb 到最新版本
```

---

## 🪟 Windows 安装指南（WSL vs 原生）

> 结论先说：`ccb/cask-w/cping` 必须和 `codex/gemini` 跑在**同一个环境**（WSL 就都在 WSL，原生 Windows 就都在原生 Windows）。最常见问题就是装错环境导致 `cping` 不通。

### 1) 前置条件：安装原生版 WezTerm（不是 WSL 版）

- 请安装 Windows 原生 WezTerm（官网 `.exe` / winget 安装都可以），不要在 WSL 里安装 Linux 版 WezTerm。
- 原因：`ccb` 在 WezTerm 模式下依赖 `wezterm cli` 管理窗格；使用 Windows 原生 WezTerm 最稳定，也最符合本项目的“分屏多模型协作”设计。

### 2) 判断方法：你到底是在 WSL 还是原生 Windows？

优先按“**你是通过哪种方式安装并运行 Claude Code/Codex**”来判断：

- **WSL 环境特征**
  - 你在 WSL 终端（Ubuntu/Debian 等）里用 `bash` 安装/运行（例如 `curl ... | bash`、`apt`、`pip`、`npm` 安装后在 Linux shell 里执行）。
  - 路径通常长这样：`/home/<user>/...`，并且可能能看到 `/mnt/c/...`。
  - 可辅助确认：`cat /proc/version | grep -i microsoft` 有输出，或 `echo $WSL_DISTRO_NAME` 非空。
- **原生 Windows 环境特征**
  - 你在 Windows Terminal / WezTerm / PowerShell / CMD 里安装/运行（例如 `winget`、PowerShell 安装脚本、Windows 版 `codex.exe`），并用 `powershell`/`cmd` 启动。
  - 路径通常长这样：`C:\\Users\\<user>\\...`，并且 `where codex`/`where claude` 返回的是 Windows 路径。

### 3) WSL 用户指南（推荐：WezTerm 承载，计算与工具在 WSL）

#### 3.1 让 WezTerm 启动时自动进入 WSL

在 Windows 上编辑 WezTerm 配置文件（通常是 `%USERPROFILE%\\.wezterm.lua`），设置默认进入某个 WSL 发行版：

```lua
local wezterm = require 'wezterm'

return {
  default_domain = 'WSL:Ubuntu', -- 把 Ubuntu 换成你的发行版名
}
```

发行版名可在 PowerShell 里用 `wsl -l -v` 查看（例如 `Ubuntu-22.04`）。

#### 3.2 在 WSL 中运行 `install.sh` 安装

在 WezTerm 打开的 WSL shell 里执行：

```bash
git clone https://github.com/bfly123/claude_code_bridge.git
cd claude_code_bridge
./install.sh install
```

提示：
- 后续所有 `ccb/cask/cask-w/cping` 也都请在 **WSL** 里运行（和你的 `codex/gemini` 保持一致）。

#### 3.3 安装后如何测试（`cping`）

```bash
ccb up codex
cping
```

预期看到类似 `Codex connection OK (...)` 的输出；失败会提示缺失项（例如窗格不存在、会话目录缺失等）。

### 4) 原生 Windows 用户指南（WezTerm 承载，工具也在 Windows）

#### 4.1 在原生 Windows 中运行 `install.ps1` 安装

在 PowerShell 里执行：

```powershell
git clone https://github.com/bfly123/claude_code_bridge.git
cd claude_code_bridge
powershell -ExecutionPolicy Bypass -File .\install.ps1 install
```

提示：
- 安装脚本会明确提醒“`ccb/cask-w` 必须与 `codex/gemini` 在同一环境运行”，请确认你打算在原生 Windows 运行 `codex/gemini`。

#### 4.2 安装后如何测试

```powershell
ccb up codex
cping
```

同样预期看到 `Codex connection OK (...)`。

### 5) 常见问题（尤其是 `cping` 不通）

#### 5.1 打开 ccb 后无法 ping 通 Codex 的原因

- **最主要原因：搞错 WSL 和原生环境（装/跑不在同一侧）**
  - 例子：你在 WSL 里装了 `ccb`，但 `codex` 在原生 Windows 跑；或反过来。此时两边的路径、会话目录、管道/窗格检测都对不上，`cping` 大概率失败。
- **Codex 会话并没有启动或已退出**
  - 先执行 `ccb up codex`，并确认 Codex 对应的 WezTerm 窗格还存在、没有被手动关闭。
- **WezTerm CLI 不可用或找不到**
  - `ccb` 在 WezTerm 模式下需要调用 `wezterm cli list` 等命令；如果 `wezterm` 不在 PATH，或 WSL 里找不到 `wezterm.exe`，会导致检测失败（可重开终端或按提示配置 `CODEX_WEZTERM_BIN`）。
- **PATH/终端未刷新**
  - 安装后请重启终端（WezTerm），再运行 `ccb`/`cping`。

---

## 🍎 macOS 安装指南

### 安装后找不到命令

如果运行 `./install.sh install` 后找不到 `ccb`、`cask`、`cping` 等命令：

**原因：** 安装目录 (`~/.local/bin`) 不在 PATH 中。

**解决方法：**

```bash
# 1. 检查安装目录是否存在
ls -la ~/.local/bin/

# 2. 检查 PATH 是否包含该目录
echo $PATH | tr ':' '\n' | grep local

# 3. 检查 shell 配置（macOS 默认使用 zsh）
cat ~/.zshrc | grep local

# 4. 如果没有配置，手动添加
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc

# 5. 重新加载配置
source ~/.zshrc
```

### WezTerm 中找不到命令

如果普通 Terminal 能找到命令，但 WezTerm 找不到：

- WezTerm 可能使用不同的 shell 配置文件
- 同时添加 PATH 到 `~/.zprofile`：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile
```

然后完全重启 WezTerm（Cmd+Q 退出后重新打开）。

---

## 🗣️ 使用场景

安装完成后，直接用自然语言与 Claude 对话即可，它会自动检测并分派任务。

**常见用法：**

- **代码审查**：*"让 Codex 帮我 Review 一下 `main.py` 的改动。"*
- **多维咨询**：*"问问 Gemini 有没有更好的实现方案。"*
- **结对编程**：*"Codex 负责写后端逻辑，我来写前端。"*
- **架构设计**：*"让 Codex 先设计一下这个模块的结构。"*
- **信息交互**：*"调取 Codex 3 轮对话，并加以总结"*

### 🎴 趣味玩法：AI 棋牌之夜！

> *"让 Claude、Codex 和 Gemini 来一局斗地主！你来发牌，大家明牌玩！"*
>
> 🃏 Claude (地主) vs 🎯 Codex + 💎 Gemini (农民)

> **提示：** 底层命令 (`cask`, `cping` 等) 通常由 Claude 自动调用，需要显式调用见命令详情。

---

## 📝 命令详情

### Codex 命令

| 命令 | 说明 |
| :--- | :--- |
| `/cask <消息>` | 后台模式：提交任务给 Codex，前台释放可继续其他任务（推荐） |
| `/cask-w <消息>` | 前台模式：提交任务并等待返回，响应更快但会阻塞 |
| `cpend [N]` | 调取当前 Codex 会话的对话记录，N 控制轮数（默认 1） |
| `cping` | 测试 Codex 连通性 |

### Gemini 命令

| 命令 | 说明 |
| :--- | :--- |
| `/gask <消息>` | 后台模式：提交任务给 Gemini |
| `/gask-w <消息>` | 前台模式：提交任务并等待返回 |
| `gpend [N]` | 调取当前 Gemini 会话的对话记录 |
| `gping` | 测试 Gemini 连通性 |

---

## 🖥️ 编辑器集成：Neovim + 多模型代码审查

<img src="assets/nvim.png" alt="Neovim 集成多模型代码审查" width="900">

> 结合 **Neovim** 等编辑器，实现无缝的代码编辑与多模型审查工作流。在你喜欢的编辑器中编写代码，AI 助手实时审查并提供改进建议。

---

## 📋 环境要求

- **Python 3.10+**
- **终端软件：** [WezTerm](https://wezfurlong.org/wezterm/) (强烈推荐) 或 tmux

---

## 🗑️ 卸载

```bash
./install.sh uninstall
```

---

<div align="center">

**Windows 完全支持** (WSL + 原生 Windows 均通过 WezTerm)

---

**测试用户群，欢迎加入**

📧 Email: bfly123@126.com
💬 WeChat: seemseam-com

<img src="assets/wechat.png" alt="微信群" width="300">

</div>
