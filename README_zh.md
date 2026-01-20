<div align="center">

# Claude Code Bridge (ccb) v5.0.1

**基于终端分屏的全新多模型交互协作工具**
**Claude & Codex & Gemini &opencode**
**超低token时时通讯，发挥cli全部功能**

<p>
  <img src="https://img.shields.io/badge/交互皆可见-096DD9?style=for-the-badge" alt="交互皆可见">
  <img src="https://img.shields.io/badge/模型皆可控-CF1322?style=for-the-badge" alt="模型皆可控">
</p>

[![Version](https://img.shields.io/badge/version-5.0.1-orange.svg)]()
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)]()

[English](README.md) | **中文**

![Showcase](assets/show.png)

<details>
<summary><b>演示动画</b></summary>

<img src="assets/readme_previews/video2.gif" alt="任意终端窗口协作演示" width="900">


<img src="assets/readme_previews/video1.gif" alt="融合vscode使用" width="900">

</details>


</div>

--- 

**简介：** 多模型协作能够有效避免模型偏见、认知漏洞和上下文限制，然而 MCP、Skills 等直接调用 API 方式存在诸多局限性可不可控性。本项目打造了一套全新的可见即可得方案。

## ⚡ 核心优势

| 特性 | 价值 |
| :--- | :--- |
| **可见可控** | 多模型分屏 CLI 挂载，所见即所得，完全掌控。 |
| **持久上下文** | 每个 AI 独立记忆，关闭后可随时恢复（`-r` 参数）。 |
| **节省 Token** | 通过守护程序仅收发送轻量级指令。 |
| **原生终端体验** | 直接集成于**tmux**（任何term推荐）或 **WezTerm** （原生win推荐）。 |

---

有人问我，和其他工作流软件的区别是什么，我用一句话回答：该项目只是不满api调用的agent交互方式而打造的**可见可控的多模型通讯方案**，该项目并不是工作流项目，但是基于它可以更容易发展出你所理想的工作流。

<h2 align="center">🚀 新版本速览</h2>

<details open>
<summary><b>v5.0.1</b> - Superpowers /all-plan + 角色感知 CCA 状态</summary>

- **/all-plan**：多模型协同规划，带 Superpowers 头脑风暴与可用性分发。
- **CCA 状态栏**：读取 `.autoflow/roles.json` 角色名（支持 `_meta.name`），按路径缓存。
- **安装器**：复制技能子目录（如 `references/`）。
- **CLI**：新增 `ccb uninstall` / `ccb reinstall`，并清理 Claude 配置。
- **路由**：项目/会话解析更严格，避免跨项目 Claude 会话。

<details>
<summary><b>详情与用法</b></summary>

用法：
```
/all-plan <需求>
```

示例：
```
/all-plan 设计一个基于 Redis 的 API 缓存层
```

亮点：
- Socratic Ladder + Superpowers Lenses + Anti-pattern 分析
- 只分发给已挂载的 CLI
- 两轮 reviewer 反馈合并设计

</details>
</details>

<details>
<summary><b>v5.0.0</b> - 任意 AI 可主控</summary>

- **解除依赖**：无需先启动 Claude，Codex 可成为主控入口
- **统一控制**：单一入口控制 CC/OC/GE
- **启动更简单**：去掉 `ccb up`，直接 `ccb ...` 或使用默认 `ccb.config`
- **挂载更自由**：更灵活的 pane 挂载与会话绑定
- **默认配置**：缺失时自动创建默认 `ccb.config`
- **守护进程自启**：`caskd`/`laskd` 在 WezTerm/tmux 按需启动
- **会话更稳**：PID 存活校验避免旧会话干扰

</details>

<details>
<summary><b>v4.0</b> - tmux 优先重构</summary>

- **全部重构**：结构更清晰，稳定性更强，也更易扩展。
- **终端后端抽象层**：统一终端层（`TmuxBackend` / `WeztermBackend`），支持自动检测与 WSL 路径处理。
- **tmux 完美体验**：稳定布局 + 窗格标题/边框 + 会话级主题（CCB 运行期间启用，退出自动恢复）。
- **支持任何终端**：只要能运行 tmux 就能获得完整多模型分屏体验（Windows 原生「建议wezterm」除外；其他都建议使用tmux）。

</details>

<details>
<summary><b>v3.0</b> - 智能守护进程</summary>

- **真·并行**：Codex/Gemini/OpenCode 多任务安全排队执行。
- **跨 AI 编排**：Claude 与 Codex 可同时驱动 OpenCode。
- **坚如磐石**：守护进程自动启动，空闲自动退出。
- **链式调用**：Codex 可委派 OpenCode 做多步流程。
- **智能打断**：Gemini 任务支持中断处理。

<details>
<summary><b>详情</b></summary>

<h3 align="center">✨ 核心特性</h3>

- **🔄 真·并行**: 同时提交多个任务给 Codex、Gemini 或 OpenCode。新的守护进程 (`caskd`, `gaskd`, `oaskd`) 会自动将它们排队并串行执行，确保上下文不被污染。
- **🤝 跨 AI 编排**: Claude 和 Codex 现在可以同时驱动 OpenCode Agent。所有请求都由统一的守护进程层仲裁。
- **🛡️ 坚如磐石**: 守护进程自我管理——首个请求自动启动，空闲 60 秒后自动关闭以节省资源。
- **⚡ 链式调用**: 支持高级工作流！Codex 可以自主调用 `oask` 将子任务委派给 OpenCode 模型。
- **🛑 智能打断**: Gemini 任务支持智能打断检测，自动处理停止信号并确保工作流连续性。

<h3 align="center">🧩 功能支持矩阵</h3>

| 特性 | `caskd` (Codex) | `gaskd` (Gemini) | `oaskd` (OpenCode) |
| :--- | :---: | :---: | :---: |
| **并行队列** | ✅ | ✅ | ✅ |
| **打断感知** | ✅ | ✅ | - |
| **响应隔离** | ✅ | ✅ | ✅ |

<details>
<summary><strong>📊 查看真实压力测试结果</strong></summary>

<br>

**场景 1: Claude & Codex 同时访问 OpenCode**
*两个 Agent 同时发送请求，由守护进程完美协调。*

| 来源 | 任务 | 结果 | 状态 |
| :--- | :--- | :--- | :---: |
| 🤖 Claude | `CLAUDE-A` | **CLAUDE-A** | 🟢 |
| 🤖 Claude | `CLAUDE-B` | **CLAUDE-B** | 🟢 |
| 💻 Codex | `CODEX-A` | **CODEX-A** | 🟢 |
| 💻 Codex | `CODEX-B` | **CODEX-B** | 🟢 |

**场景 2: 递归/链式调用**
*Codex 自主驱动 OpenCode 执行 5 步工作流。*

| 请求 | 退出码 | 响应 |
| :--- | :---: | :--- |
| **ONE** | `0` | `CODEX-ONE` |
| **TWO** | `0` | `CODEX-TWO` |
| **THREE** | `0` | `CODEX-THREE` |
| **FOUR** | `0` | `CODEX-FOUR` |
| **FIVE** | `0` | `CODEX-FIVE` |

</details>
</details>
</details>

---

<h3 align="center">🧠 介绍 CCA (Claude Code Autoflow)</h3>

释放 `ccb` 的全部潜力 —— **CCA** 是基于本桥接工具构建的高级工作流自动化系统。

*   **工作流自动化**: 智能任务分配和自动化状态管理。
*   **无缝集成**: 原生支持 v3.0 守护进程架构。

[👉 在 GitHub 上查看项目](https://github.com/bfly123/claude_code_autoflow)

**通过 CCB 安装:**
```bash
ccb update cca
```

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
ccb                    # 按 ccb.config 启动（默认：四个全开）
ccb codex gemini       # 同时启动两个
ccb codex gemini opencode claude  # 同时启动四个（空格分隔）
ccb codex,gemini,opencode,claude  # 同时启动四个（逗号分隔）
ccb -r codex gemini     # 恢复 Codex + Gemini 上次会话
ccb -a codex gemini opencode  # 自动权限模式，启动多个
ccb -a -r codex gemini opencode claude  # 自动 + 恢复（四个全开）

tmux 提示：CCB 的 tmux 状态栏/窗格标题主题只会在 CCB 运行期间启用。

布局规则：当前 pane 对应 providers 列表的最后一个。额外 pane 顺序为 `[cmd?, providers 反序]`；第一个额外 pane 在右上，其后先填满左列（从上到下），再填右列（从上到下）。例：4 个 pane 左2右2，5 个 pane 左2右3。
提示：`ccb up` 已移除，请使用 `ccb ...` 或配置 `ccb.config`。
```

### 常用参数
| 参数 | 说明 | 示例 |
| :--- | :--- | :--- |
| `-r` | 恢复上次会话上下文 | `ccb -r` |
| `-a` | 全自动模式，跳过权限确认 | `ccb -a` |
| `-h` | 查看详细帮助信息 | `ccb -h` |
| `-v` | 查看当前版本和检测更新 | `ccb -v` |

### ccb.config
默认查找顺序：
- `.ccb_config/ccb.config`（项目级）
- `~/.ccb/ccb.config`（全局）

推荐的简化格式：
```text
codex,gemini,opencode,claude
```

开启 cmd pane（默认标题/命令）：
```text
codex,gemini,opencode,claude,cmd
```

cmd pane 作为第一个额外 pane 参与布局，不会改变当前 pane 对应的 AI。

### 后续更新
```bash
ccb update              # 更新 ccb 到最新版本
ccb update 4            # 更新到 v4.x.x 最高版本
ccb update 4.1          # 更新到 v4.1.x 最高版本
ccb update 4.1.2        # 更新到指定版本 v4.1.2
ccb update cca          # 仅更新 CCA (Claude Code Autoflow)
ccb uninstall           # 卸载 ccb 并清理配置
ccb reinstall           # 清理后重新安装
```

---

<details>
<summary><b>🪟 Windows 安装指南（WSL vs 原生）</b></summary>

> 结论先说：`ccb/cask/cping/cpend` 必须和 `codex/gemini` 跑在**同一个环境**（WSL 就都在 WSL，原生 Windows 就都在原生 Windows）。最常见问题就是装错环境导致 `cping` 不通。

补充：安装脚本会为 Claude/Codex 的 skills 自动安装对应平台的 `SKILL.md` 版本：
- Linux/macOS/WSL：bash heredoc 模板（`SKILL.md.bash`）
- 原生 Windows：PowerShell here-string 模板（`SKILL.md.powershell`）

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
- 后续所有 `ccb/cask/cping/cpend` 也都请在 **WSL** 里运行（和你的 `codex/gemini` 保持一致）。

#### 3.3 安装后如何测试（`cping`）

```bash
ccb codex
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
- 安装脚本会明确提醒“`ccb/cask/cping/cpend` 必须与 `codex/gemini` 在同一环境运行”，请确认你打算在原生 Windows 运行 `codex/gemini`。
- 安装脚本优先使用 `pwsh.exe`（PowerShell 7+）；如果没有则使用 `powershell.exe`。
- 如果检测到 WezTerm 配置文件，安装脚本会尝试设置 `config.default_prog` 为 PowerShell（会插入 `-- CCB_WEZTERM_*` 区块；若已有 `default_prog` 会先询问是否覆盖）。

#### 4.2 安装后如何测试

```powershell
ccb codex
cping
```

同样预期看到 `Codex connection OK (...)`。

### 5) 常见问题（尤其是 `cping` 不通）

#### 5.1 打开 ccb 后无法 ping 通 Codex 的原因

- **最主要原因：搞错 WSL 和原生环境（装/跑不在同一侧）**
  - 例子：你在 WSL 里装了 `ccb`，但 `codex` 在原生 Windows 跑；或反过来。此时两边的路径、会话目录、管道/窗格检测都对不上，`cping` 大概率失败。
- **Codex 会话并没有启动或已退出**
  - 先执行 `ccb codex`（或在 ccb.config 中启用 codex），并确认 Codex 对应的 WezTerm 窗格还存在、没有被手动关闭。
- **WezTerm CLI 不可用或找不到**
  - `ccb` 在 WezTerm 模式下需要调用 `wezterm cli list` 等命令；如果 `wezterm` 不在 PATH，或 WSL 里找不到 `wezterm.exe`，会导致检测失败（可重开终端或按提示配置 `CODEX_WEZTERM_BIN`）。
- **PATH/终端未刷新**
  - 安装后请重启终端（WezTerm），再运行 `ccb`/`cping`。
- **原生 Windows 的 WezTerm：能把文字发到 Codex，但没有“回车提交”**
  - 设置环境变量 `CCB_WEZTERM_ENTER_METHOD=key`（用 `wezterm cli send-key` 发送真实按键事件；如果你的 WezTerm 版本太旧请升级）。

</details>

---

<details>
<summary><b>🍎 macOS 安装指南</b></summary>

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

</details>

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
| `cpend [N]` | 调取当前 Codex 会话的对话记录，N 控制轮数（默认 1） |
| `cping` | 测试 Codex 连通性 |

### Gemini 命令

| 命令 | 说明 |
| :--- | :--- |
| `/gask <消息>` | 后台模式：提交任务给 Gemini |
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
ccb uninstall
ccb reinstall

# 备用方式：
./install.sh uninstall
```

---

<details>
<summary><b>更新历史</b></summary>

### v5.0.1
- **技能更新**：新增 `/all-plan`（Superpowers 头脑风暴 + 可用性分发）；Codex 侧新增 `lping/lpend`；`gask` 在 `CCB_DONE` 场景保留简要执行摘要。
- **CCA 状态栏**：从 `.autoflow/roles.json` 读取角色名（支持 `_meta.name`），并按路径缓存。
- **安装器**：安装技能时复制子目录（如 `references/`）。
- **CLI**：新增 `ccb uninstall` / `ccb reinstall`，并清理 Claude 配置。
- **路由**：项目/会话解析更严格（优先 `.ccb_config`，避免跨项目 Claude 会话）。

### v5.0.0
- **解除依赖**：无需先启动 Claude，Codex 也可以作为主 CLI
- **统一控制**：单一入口控制 Claude/OpenCode/Gemini
- **启动简化**：移除 `ccb up`，默认 `ccb.config` 自动生成
- **挂载更自由**：更灵活的 pane 挂载与会话绑定
- **守护进程自启**：`caskd`/`laskd` 在 WezTerm/tmux 按需启动
- **会话更稳**：PID 存活校验避免旧会话干扰

### v4.1.3
- **Codex 配置修复**: 自动迁移过期的 `sandbox_mode = "full-auto"` 为 `"danger-full-access"`，修复 Codex 无法启动的问题
- **稳定性**: 修复了快速退出的命令可能在设置 `remain-on-exit` 之前关闭 pane 的竞态条件
- **Tmux**: 更稳健的 pane 检测机制 (优先使用稳定的 `$TMUX_PANE` 环境变量)，并增强了分屏目标失效时的回退处理

### v4.1.2
- **性能优化**: 为 tmux 状态栏 (git 分支 & ccb 状态) 增加缓存，大幅降低系统负载
- **严格模式**: 明确要求在 `tmux` 内运行; 移除不稳定的自动 attach 逻辑，避免环境混乱
- **CLI**: 新增 `--print-version` 参数用于快速版本检查

### v4.1.1
- **CLI 修复**: 修复 `ccb` 在 tmux 中重启时参数丢失 (如 `-a`) 的问题
- **体验优化**: 非交互式环境下提供更清晰的错误提示
- **安装**: 强制更新 skills 以确保应用最新版本

### v4.1.0
- **异步护栏**: `cask/gask/oask` 执行后输出护栏提示，防止 Claude 继续轮询
- **同步模式**: 添加 `--sync` 参数，Codex 调用时跳过护栏提示
- **Codex Skills 更新**: `oask/gask` 使用 `--sync` 静默等待

### v4.0
- **全部重构**：整体架构重写，更清晰、更稳定
- **tmux 完美支持**：分屏/标题/边框/状态栏一体化体验
- **支持任何终端**：除 Windows 原生环境外，强烈建议统一迁移到 tmux 下使用

### v3.0.0
- **智能守护进程**: `caskd`/`gaskd`/`oaskd` 支持 60秒空闲超时和并行队列
- **跨 AI 协作**: 支持多个 Agent (Claude/Codex) 同时调用同一个 Agent (OpenCode)
- **打断检测**: Gemini 现在支持智能打断处理
- **链式执行**: Codex 可以调用 `oask` 驱动 OpenCode
- **稳定性**: 健壮的队列管理和锁文件机制
