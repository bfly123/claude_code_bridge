<div align="center">

# CCB v6(Linux) - 无限并发 agents 版本

**终端分屏原生多 Agent Runtime**
**Claude · Codex · Gemini · OpenCode · Droid**
**可见并发、原生通信、项目级运行时**

<p>
  <img src="https://img.shields.io/badge/交互皆可见-096DD9?style=for-the-badge" alt="交互皆可见">
  <img src="https://img.shields.io/badge/模型皆可控-CF1322?style=for-the-badge" alt="模型皆可控">
</p>

[![Version](https://img.shields.io/badge/version-6.0.7-orange.svg)]()
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

**简介：** CCB v6 是“无限并发 agent 版本”。它把终端分屏协作提升为原生多 agent runtime，让 agent 可以并排运行、保持独立角色与人格，并通过稳定的内建通信层彼此调用。

## 为什么多 Agent 并行很重要

多 agent 并行并不只是“多开几个 pane”。在 CCB 里，每个 agent 都可以拥有完全独立的角色、任务流、skill 库和人格。

CCB 为稳定的 agent 间通信和几乎无限量的 agent 互相调用提供运行时基础。支持任意命名和桌面窗口排列, 支持每个agent独立控制,支持派发和单点通讯.



## 🚀 用户命令

- `ccb`  基于terminal 在项目目录打开ccb
- `ccb -s safe模式`
- `ccb -n 重建项目ccb`
- `ccb kill 关闭ccb`
- `ccb kill -f 深度清理式退出`

## 💬 通讯使用

在 provider / agent runtime 内

- `/ask all  "sync on the latest repo state"` 会把一条消息广播给所有存活 agent。
- `/ask reviewer "review the new parser change"` 会把任务定向发给[reviewer]命名 agent。

典型模式：

- 用 `ask all` 做一次广播或全局同步
- 用 `ask agent_name` 做定向委派
- 通过skill隐式调用, agent自己会使用ask ,目前自动安装skill到codex claude 等provider
- 如果只是偶尔需要手动查看回复，`pend` 和 `watch` 仍然可用，但它们属于次级查看工具

## 🛠 配置控制

`ccb` 的行为由 `.ccb/ccb.config` 控制。这个文件直接定义 agent 名字、pane 分屏方式，以及某个 agent 是 `inplace` 运行还是进入独立 git worktree。

快速规则：

- `agent_name:provider` 定义一个 agent；其中 `agent_name` 同时也是 pane 标题和逻辑运行时名字。
- `cmd` 表示增加一个 shell pane。
- `;` 表示左右分栏。
- `,` 表示上下分栏。
- 默认工作区模式是 `inplace`。如果某个 agent 需要独立 git worktree(可以避免冲突)，就写成 `agent_name:provider(worktree)`。

示例：

```text
cmd; writer:codex, reviewer:claude; qa:gemini(worktree)
```

这个布局表示：

- 左侧 pane：`cmd`
- 右侧整体：上下堆叠
- 右上 pane：`writer`
- 右下区域：`reviewer` 和 `qa` 左右并排
- `qa` 使用独立 git worktree；`writer` 和 `reviewer` 在主项目目录中以 inplace 方式运行.



<h2 align="center">🚀 新版本速览</h2>

历史说明：下面较旧的发布记录里仍可能出现 `askd`、旧 flag 或已移除命令。这些内容仅作为 changelog 历史保留，不代表当前 CLI 入口。

<details open>
<summary><b>v6.0.7</b> - 生命周期 authority 与停机稳定性增强</summary>

- **Keeper 持有生命周期 authority**：keeper 现在通过权威 `lifecycle.json`、generation fence 和 namespace epoch 跟踪来推进项目生命周期
- **Mounted 状态读路径修复**：`ping ccbd` 与 `ping agent` 现在从当前 authority 读取 mounted/runtime 状态，不再在恢复后漂移到旧的失败视图
- **Shutdown 事务加固**：`ccb kill` 和 `ccb kill -f` 现在会在停机事务里终结所有非终态 job，重启后不会再通过 restore 或 auto-retry 复活旧执行
- **真实黑盒复现已收口**：真实 `ask -> kill -f -> restart` 路径现在会稳定收口为 `project_shutdown`，不再残留活动执行

</details>

<details>
<summary><b>v6.0.6</b> - Agent 隔离稳定性增强与 kill 生命周期修复</summary>

- **Agent 隔离稳定性增强**：Codex、Claude、Gemini 的 managed agent 会把会话状态稳定保存在项目级 `.ccb/agents/<agent>/provider-state/...` 下
- **重启继承更安全**：重启只恢复对应 managed agent 自己的历史，不再因为工作目录相同而吸收手工运行 provider 的对话
- **项目 Provider Dotfile 保护**：managed 启动不再改写项目级 `.claude`、`.gemini` 或 `.codex` provider dotfiles
- **Kill 生命周期修复**：`ccb kill` 主动销毁当前项目 tmux session 后，交互式 `ccb` 不再误报前台 attach 失败

</details>

<details>
<summary><b>v6.0.5</b> - Agent 隔离稳定性增强</summary>

- **Agent 隔离稳定性增强**：Codex、Claude、Gemini 的 managed agent 会把会话状态稳定保存在项目级 `.ccb/agents/<agent>/provider-state/...` 下
- **重启继承更安全**：重启只恢复对应 managed agent 自己的历史，不再因为工作目录相同而吸收手工运行 provider 的对话
- **项目 Provider Dotfile 保护**：managed 启动不再改写项目级 `.claude`、`.gemini` 或 `.codex` provider dotfiles

</details>

<details>
<summary><b>v6.0.4</b> - 旧版升级兼容热修复</summary>

- **向后兼容的 Release 资产**：Linux release tarball 现在会额外带一个兼容别名，旧版 6.x updater 即使误把资产名当作解压目录，也仍然能找到安装器
- **旧客户端升级链路恢复**：现有 `v6.0.1` 和 `v6.0.2` 安装现在可以直接升级到最新稳定版，不需要先拥有修过的本地 updater
- **新 updater 仍保持正确**：当前 runtime 继续按正确的解压目录工作，不依赖这个兼容别名

</details>

<details>
<summary><b>v6.0.3</b> - 自升级 tarball 热修复</summary>

- **Release 升级修复**：`ccb update` 现在会正确定位解压后的 release 目录，不再把 `.tar.gz` 资产名当成目录
- **安装器接力恢复**：自升级现在能正确找到 release 包里的 `install.sh` 并走完整替换流程
- **Release 构建卫生**：Linux release 打包现在会忽略本地 `.ccb-requests/` 残留，正式构建不再被运行时垃圾阻塞

</details>

<details>
<summary><b>v6.0.2</b> - caller 归因修复、邮箱路由稳定化与 macOS 安装提醒</summary>

- **Caller 身份归因修复**：`ccb ask` 现在会保留真实发起 agent 身份，reply 不再误记成 `user`
- **Reply 路由更稳定**：异步委派任务的回复现在会回到正确邮箱链路，包括 `cmd` 锚点场景
- **Mixed-Case Agent 恢复修复**：配置里使用大小写混合的 agent 名称时，布局恢复与启动不再漂移
- **macOS Homebrew 提醒**：`install.sh` 现在会在缺少 Homebrew 时先给出明确警告，再继续 tmux 等依赖安装说明

</details>

<details>
<summary><b>v6.0.1</b> - Release 归档清理与更安全的升级解压</summary>

- **源码归档清理**：移除误提交的 pytest 临时产物，GitHub 源码归档重新保持干净
- **更严格的 tar 校验**：升级解压前会先拒绝不安全的 symlink 目标
- **失败提示更直白**：遇到不安全归档时，会明确提示使用 release 资产或干净源码包
- **回归测试补齐**：新增测试阻止临时测试产物再次被跟踪进仓库

</details>

<details>
<summary><b>v6.0.0</b> - 原生多 Agent Runtime、稳定原生通信、仅 Linux/WSL 自动升级</summary>

**🚀 全新运行时方向：**
- **无限并发 agent 基础**：CCB v6 被定义为几乎无限量 agent 互调与编排的运行时底座
- **Agent 身份独立**：每个 agent 都可以拥有不同的角色、任务归属、skill 库和人格
- **公开命令面收口**：面向用户的公开工作流继续聚焦 `ccb`、`ccb -s`、`ccb -n`、`ccb kill`、`ccb kill -f`

**🧱 项目重建语义：**
- **保留配置清理旧态**：首次在 pre-6 项目中执行 `ccb` 时，会保留 `.ccb/ccb.config`，清除其余旧 `.ccb` 运行时状态，然后在本地重建
- **运行时标记**：现代项目会写入 `.ccb/project-runtime.json`，避免把当前 runtime 误判为旧状态
- **Worktree 安全护栏**：CCB 管理的 git worktree 若存在脏改动或未合并分支，仍会阻断破坏性清理并要求用户先处理

**🔄 升级策略：**
- **仅 Linux/WSL**：`ccb update` 在 6.x 线目前只对 Linux/WSL 开放
- **仅使用 Release 资产升级**：每个版本仍会一起发布源码 tag，但 `ccb update` 在 6.x 线只安装 GitHub release 资产，不再使用源码压缩包
- **稳定发布升级**：默认升级目标改为最新稳定 release，而不是漂移的 `main`
- **Major 升级确认**：升级到 `6.0.0` 时会先要求明确确认，再替换已安装 runtime

**🤖 Provider 稳定性：**
- **Gemini 多轮稳定性**：Gemini 完成判定现在会持续跟踪 tool activity，不会在第一句稳定规划文本上提前结束

</details>

<details>
<summary><b>v5.3.0</b> - CLI 收口、显式 worktree 模式、Gemini 完成判定修复</summary>

**🚀 面向用户的 CLI 收口：**
- **主入口更清晰**：公开工作流收敛为 `ccb`、`ccb -s`、`ccb -n`、`ccb kill`、`ccb kill -f`
- **模型控制面保留**：`ask`、`ping`、`pend`、`watch` 继续保留给 agent 侧编排使用，但不再挤占主帮助入口

**🧱 工作区语义显式化：**
- **默认 inplace**：compact `ccb.config` 现在默认展开为 `workspace_mode='inplace'`
- **显式隔离**：只有写成 `agent:provider(worktree)` 时，agent 才会进入独立 git worktree
- **Agent 变更更稳**：新增 agent 不再影响已有 worktree；删除或改名 worktree agent 时，干净分支会自动退休，脏分支或未合并分支会阻断并提醒

**🛠 重建与恢复加固：**
- **保留配置重建**：`ccb -n` 会重建项目运行时状态，但保留 `.ccb/ccb.config`
- **陈旧注册清理**：启动与重建前会先清理已注册但路径丢失的 git worktree
- **Kill 提醒**：`ccb kill` 在发现 worktree agent 仍有未合并或脏状态时会显著提醒用户

**🤖 Gemini 完成判定修复：**
- **不再首轮提前结束**：Gemini 轮询完成检测现在会跟踪 tool call 活动，不会再把第一轮稳定的“我先开始分析/搜索”文本误判成最终回复

</details>

<details>
<summary><b>v5.2.6</b> - 异步通信修复 & Gemini 0.29 兼容</summary>

**🔧 Gemini CLI 0.29.0 适配：**
- **双哈希策略**：会话路径发现同时支持 basename 和 SHA-256 格式
- **自动启动**：`ccb-ping` 和 `ccb-mounted` 新增 `--autostart` 标志，可自动拉起离线 provider
- **清理路径**：僵尸会话清理现已统一收敛到 `ccb kill -f`

**🔗 异步通信修复：**
- **OpenCode 死锁**：修复会话 ID 固定导致第二次异步调用必定失败的问题
- **旧兼容完成检测**：旧文本型 provider 在降级模式下仍可容忍不完全匹配的 `CCB_DONE`
- **req_id 正则**：`opencode_comm.py` 同时匹配旧 hex 和新时间戳格式
- **Gemini 空闲超时**：Gemini 漏写 `CCB_DONE` 时自动检测回复完成（默认 15s，可通过 `CCB_GEMINI_IDLE_TIMEOUT` 调整）
- **Gemini Prompt 加固**：强化指令格式，降低 `CCB_DONE` 遗漏率

**🛠 其他修复：**
- **lpend**：registry 过期时优先使用更新鲜的 Claude 会话路径

</details>

<details>
<summary><b>v5.2.5</b> - 异步护栏加固</summary>

**🔧 异步轮次停止修复：**
- **全局护栏**：在 `claude-md-ccb.md` 中添加强制 `Async Guardrail` 规则，同时覆盖 `/ask` 技能和直接 `Bash(ask ...)` 调用
- **标记一致性**：`bin/ask` 现在输出 `[CCB_ASYNC_SUBMITTED provider=xxx]`，与其他 provider 脚本格式统一
- **技能精简**：Ask 技能规则引用全局护栏并保留本地兜底，单一权威源

此修复防止 Claude 在提交异步任务后继续轮询/休眠。

</details>

<details>
<summary><b>v5.2.3</b> - 项目内历史记录 & 旧目录兼容</summary>

**📂 项目内历史记录：**
- **本地存储**：自动导出改为写入 `./.ccb/history/`
- **范围收敛**：仅对当前工作目录触发自动迁移/导出
- **Claude /continue**：新增技能，直接 `@` 最新历史文件

**🧩 旧目录兼容：**
- **自动迁移**：检测到 `.ccb_config` 时自动升级为 `.ccb`
- **兼容查找**：过渡期仍可解析旧目录内的会话

这些更新让交接文件只留在项目内，升级路径更平滑。

</details>

<details>
<summary><b>v5.2.2</b> - 会话切换跟踪 & 自动提取</summary>

**🔁 会话切换跟踪：**
- **上一条会话字段**：`.claude-session` 记录 `old_claude_session_id` / `old_claude_session_path` 与 `old_updated_at`
- **自动导出**：切换会话时自动生成 `./.ccb/history/claude-<timestamp>-<old_id>.md`
- **内容去噪**：过滤协议标记/护栏，保留工具调用摘要

这些更新让会话交接更可靠、更易追踪。

</details>

<details>
<summary><b>v5.2.0</b> - 历史 mail bridge 版本</summary>

这个版本引入了旧的邮件网关路径。该路径现在已不再属于受支持的 agent-first CLI 表面，仅作为清理过渡期遗留代码保留。

</details>

<details>
<summary><b>v5.1.2</b> - Daemon 与 Hook 稳定性</summary>

**🔧 修复与改进：**
- **Claude Completion Hook**：统一 askd 为 Claude 触发完成回调
- **askd 生命周期**：askd 绑定 CCB 生命周期，避免残留守护进程
- **挂载检测**：`ccb-mounted` 统一使用 ping 检测（兼容统一 askd）
- **状态文件查找**：`askd_client` 兜底使用 `CCB_RUN_DIR` 查找状态文件

详见 [CHANGELOG.md](CHANGELOG.md)。

</details>

<details>
<summary><b>v5.1.1</b> - 统一 Daemon + Bug 修复</summary>

**🔧 Bug 修复与改进：**
- **统一 Daemon**：所有 provider 现在使用统一的 askd daemon 架构
- **安装/卸载**：修复安装和卸载相关 bug
- **进程管理**：修复 kill/终止问题

详见 [CHANGELOG.md](CHANGELOG.md)。

</details>

<details>
<summary><b>v5.1.0</b> - 统一命令系统 + 历史原生 Windows 实验</summary>

**🚀 统一命令** - 用 agent-first 工作流替代各 provider 独立命令：

| 旧命令 | 新统一命令 |
|--------|-----------|
| `cask`, `gask`, `oask`, `dask`, `lask` | `ccb ask <agent> [from <sender>] <message>` |
| `cping`, `gping`, `oping`, `dping`, `lping` | `ccb ping <agent\|all>` |
| `cpend`, `gpend`, `opend`, `dpend`, `lpend` | `ccb pend <agent\|job_id> [N]` |

**支持的 provider:** `gemini`, `codex`, `opencode`, `droid`, `claude`

**🪟 历史原生 Windows 实验：**
- 早期版本曾探索原生 Windows 分屏运行路径
- 后台执行使用 PowerShell + `DETACHED_PROCESS`
- 大消息通过 stdin 方式传递
- 该后端现已移除；未来原生 Windows mux 路线将围绕 `psmux` 重建

**📦 新技能：**
- `/ask <agent> <message>` - 向命名 agent 提交任务
- `/ping <agent|all>` - 检查挂载状态
- `/pend <agent|job_id> [N]` - 查看最新回复

详见 [CHANGELOG.md](CHANGELOG.md)。

</details>

<details>
<summary><b>v5.0.5</b> - Droid 调度工具与安装</summary>

- **Droid**：新增调度工具（`ccb_ask_*` 以及 `cask/gask/lask/oask` 别名）。
- **安装**：新增 `ccb droid setup-delegation` 用于 MCP 注册。
- **安装器**：检测到 `droid` 时自动注册（可通过环境变量关闭）。

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
- **项目 askd 自启**：项目 askd 与 provider runtime 会在项目 tmux namespace 中按需启动
- **会话更稳**：PID 存活校验避免旧会话干扰

</details>

<details>
<summary><b>v4.0</b> - tmux 优先重构</summary>

- **全部重构**：结构更清晰，稳定性更强，也更易扩展。
- **终端运行时收口**：运行时逐步收敛为单一 tmux pane/control 模型，不再并行维护双终端后端。
- **tmux 完美体验**：稳定布局 + 窗格标题/边框 + 会话级主题（CCB 运行期间启用，退出自动恢复）。
- **支持任何终端**：只要能运行 tmux，就能获得完整多模型分屏体验。

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

- **🔄 真·并行**: 同时提交多个任务给 Codex、Gemini 或 OpenCode。provider runtime 会自动排队并串行执行，确保上下文不被污染。
- **🤝 跨 AI 编排**: Claude 和 Codex 现在可以同时驱动 OpenCode Agent。所有请求都由项目 askd 层统一仲裁。
- **🛡️ 坚如磐石**: 运行时层自我管理，首个请求自动启动，空闲后自动关闭以节省资源。
- **⚡ 链式调用**: 支持高级工作流！Codex 可以自主调用 `oask` 将子任务委派给 OpenCode 模型。
- **🛑 智能打断**: Gemini 任务支持智能打断检测，自动处理停止信号并确保工作流连续性。

<h3 align="center">🧩 功能支持矩阵</h3>

| 特性 | Codex | Gemini | OpenCode |
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

## 🚀 快速开始

**第一步：** 准备可运行 `tmux` 的环境（Linux/macOS/WSL）

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

> 当前分屏运行的稳定主路径仍是 Linux/macOS/WSL + `tmux`。原生 Windows mux 正在按 `psmux` 方向重构。

```powershell
git clone https://github.com/bfly123/claude_code_bridge.git
cd claude_code_bridge
powershell -ExecutionPolicy Bypass -File .\install.ps1 install
```

</details>

### 启动
```bash
ccb                    # 按 .ccb/ccb.config 启动默认 agent
ccb -s                 # 安全启动：保留 agent 自身配置的权限策略
ccb -n                 # 重建 .ccb（保留 ccb.config），再重新启动
ccb kill               # 停止当前项目相关后台
ccb kill -f            # 强制清理项目残留后再配合 ccb -n 使用
```

tmux 提示：CCB 的 tmux 状态栏/窗格标题主题只会在 CCB 运行期间启用。
tmux 提示：在 tmux 内可以按 `Ctrl+b` 然后按 `Space` 来切换布局；可以连续按，多次循环切换不同布局。

布局规则：当前 pane 对应目标列表的最后一个 agent。额外 pane 顺序为 `[cmd?, 其他目标反序]`；第一个额外 pane 在右上，其后先填满左列（从上到下），再填右列（从上到下）。例：4 个 pane 左2右2，5 个 pane 左2右3。
提示：`ccb up` 已移除，请使用 `ccb ...` 或配置 `.ccb/ccb.config`。

### 常用参数
| 参数 | 说明 | 示例 |
| :--- | :--- | :--- |
| `-s` | 安全启动；关闭 CLI 自动权限覆盖 | `ccb -s` |
| `-n` | 重建 `.ccb`（保留 `ccb.config`）后再启动 | `ccb -n` |
| `-h` | 查看详细帮助信息 | `ccb -h` |
| `-v` | 查看当前版本和检测更新 | `ccb -v` |

### ccb.config
默认查找顺序：
- `.ccb/ccb.config`（项目级）
- `~/.ccb/ccb.config`（全局）

只支持紧凑格式：
```text
writer:codex,reviewer:claude
```

开启 cmd pane（默认标题/命令）：
```text
agent1:codex,agent2:codex,agent3:claude,cmd
```

规则：
- 每个 agent 项都必须写成 `agent_name:provider`
- `cmd` 是独立保留字，只表示 shell pane，不是 agent 名
- `;` 表示左右分栏
- `,` 表示上下分栏
- `(...)` 表示显式分组
- 每个 agent 项都会展开成固定默认值：`target='.'`、`workspace_mode='inplace'`、`restore='auto'`、`permission='manual'`
- 如果希望某个 agent 使用独立 git worktree，请显式写成 `agent_name:provider(worktree)`
- 缺失项目配置时会自动生成：`codex:codex,claude:claude`
- cmd pane 作为第一个额外 pane 参与布局，不会改变当前 pane 对应的 AI

### 后续更新
CCB v6 目前只有 Linux/WSL 支持 `ccb update`。major 升级会整体替换已安装 runtime；旧项目第一次执行 `ccb` 时，会保留 `.ccb/ccb.config`，清理其余旧 `.ccb` 状态后再原地重建。

```bash
ccb update              # 更新 ccb 到最新稳定版本
ccb update 6            # 更新到 v6.x.x 最高版本
ccb update 6.0          # 更新到 v6.0.x 最高版本
ccb update 6.0.5        # 更新到指定版本
ccb uninstall           # 卸载 ccb 并清理配置
ccb reinstall           # 清理后重新安装
```

---

<details>
<summary><b>🪟 Windows 环境说明</b></summary>

> 结论先说：`ccb` 和底层 agent CLI 必须跑在**同一个环境**（WSL 就都在 WSL，原生 Windows 就都在原生 Windows）。最常见问题就是装错环境，导致项目启动或 agent 挂载失败。

补充：安装脚本会为 Claude/Codex 的 skills 自动安装对应平台的 `SKILL.md` 版本：
- Linux/macOS/WSL：bash heredoc 模板（`SKILL.md.bash`）
- 原生 Windows：PowerShell here-string 模板（`SKILL.md.powershell`）

### 1) 当前后端状态

- 当前分屏 runtime 已收口为 `tmux` 单一路径。
- 现阶段稳定使用方式是 Linux/macOS/WSL + `tmux`。
- 原生 Windows mux 方案正在围绕 `psmux` 设计，见 [docs/ccbd-windows-psmux-plan.md](docs/ccbd-windows-psmux-plan.md)。

### 2) 判断方法：你到底是在 WSL 还是原生 Windows？

优先按“**你是通过哪种方式安装并运行 Claude Code/Codex**”来判断：

- **WSL 环境特征**
  - 你在 WSL 终端（Ubuntu/Debian 等）里用 `bash` 安装/运行（例如 `curl ... | bash`、`apt`、`pip`、`npm` 安装后在 Linux shell 里执行）。
  - 路径通常长这样：`/home/<user>/...`，并且可能能看到 `/mnt/c/...`。
  - 可辅助确认：`cat /proc/version | grep -i microsoft` 有输出，或 `echo $WSL_DISTRO_NAME` 非空。
- **原生 Windows 环境特征**
  - 你在 Windows Terminal / PowerShell / CMD 里安装/运行（例如 `winget`、PowerShell 安装脚本、Windows 版 `codex.exe`），并用 `powershell`/`cmd` 启动。
  - 路径通常长这样：`C:\\Users\\<user>\\...`，并且 `where codex`/`where claude` 返回的是 Windows 路径。

### 3) 当前推荐路径

- 如果你要使用当前稳定的分屏与守护逻辑，请把 `ccb` 和所有 agent CLI 都放在 WSL 里运行，并使用 `tmux`。
- 如果你现在必须跑在原生 Windows，请保持环境一致，但原生分屏编排仍属于过渡态，直到 `psmux` 路线落地。

#### 3.1 在 WSL 中运行 `install.sh` 安装

在 WSL shell 里执行：

```bash
git clone https://github.com/bfly123/claude_code_bridge.git
cd claude_code_bridge
./install.sh install
```

提示：
- 后续所有 `ccb` 与底层 agent CLI 也都请在 **WSL** 里运行（和你的 `codex/gemini` 保持一致）。

### 4) 安装后如何测试

```bash
ccb
```

预期会按 `.ccb/ccb.config` 启动项目 agent；如果失败，通常会直接提示缺失项（例如 `tmux` 不存在、环境不一致、配置问题等）。

### 5) 常见问题

#### 5.1 打开 `ccb` 后启动失败的常见原因

- **最主要原因：搞错 WSL 和原生环境（装/跑不在同一侧）**
  - 例子：你在 WSL 里装了 `ccb`，但 `codex` 在原生 Windows 跑；或反过来。此时两边的路径、会话目录、管道/窗格检测都对不上，启动大概率失败。
- **tmux 不可用或找不到**
  - 当前分屏 runtime 依赖 `tmux`；如果 `tmux` 不在 PATH，pane 编排与检测会失败。
- **PATH/终端未刷新**
  - 安装后请重启 shell，再运行 `ccb`。

</details>

---

<details>
<summary><b>🍎 macOS 安装指南</b></summary>

### 安装后找不到命令

如果运行 `./install.sh install` 后找不到 `ccb`：

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

### tmux shell 中找不到命令

如果普通 Terminal 能找到命令，但 tmux 内 shell 找不到：

- tmux 可能走了不同的 shell 初始化路径
- 同时添加 PATH 到 `~/.zprofile`：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile
```

然后完全重启 tmux server：

```bash
tmux kill-server
```

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

> **提示：** CCB v6 面向用户的公开项目运行工作流被刻意压缩为 `ccb`、`ccb -s`、`ccb -n`、`ccb kill`、`ccb kill -f`。内部控制面命令依然存在，用于 agent 侧编排，但不属于用户侧启动/重建命令表面。

---

## 🛠️ 用户侧 CLI

CCB v6 面向用户的公开项目运行工作流只保留这 5 个主命令：

- **`ccb`** - 默认启动路径；按 `.ccb/ccb.config` 启动项目 agent
- **`ccb -s`** - 安全启动；保留每个 agent 自身配置/默认权限策略
- **`ccb -n`** - 交互确认后重建项目 `.ccb` 状态，仅保留 `ccb.config`
- **`ccb kill`** - 停止当前项目 runtime
- **`ccb kill -f`** - 在执行 `ccb -n` 前强制清理项目残留
  - 也可作为 `.ccb` 还在但 `ccb.config` 丢失/损坏时的恢复入口

模型侧控制面命令仍然保留，用于 agent 间通讯和自动化，但这里不再把它们当成用户主命令展开说明。

### 跨平台支持
- **Linux/macOS/WSL**: 使用 `tmux` 作为终端后端
- **原生 Windows**: mux runtime 正在按 `psmux` 重构；当前分支不再保留并行 legacy native backend

### Completion Hook
- 任务完成后自动通知发起者
- 支持按 caller 定向回调目标 (claude/codex/droid)
- 兼容当前分支使用的 tmux 后端
 - 前台 ask 默认关闭 hook，除非设置 `CCB_COMPLETION_HOOK_ENABLED`

---

## Legacy Cleanup 说明

旧 `mail` 子系统和 `maild` 已从仓库中移除。当前 runtime 以项目目录和 `.ccb/ccb.config` 为中心，旧状态可以清理后重建。

---

## 🖥️ 编辑器集成：Neovim + 多模型代码审查

<img src="assets/nvim.png" alt="Neovim 集成多模型代码审查" width="900">

> 结合 **Neovim** 等编辑器，实现无缝的代码编辑与多模型审查工作流。在你喜欢的编辑器中编写代码，AI 助手实时审查并提供改进建议。

---

## 📋 环境要求

- **Python 3.10+**
- **终端软件：** `tmux`

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

### v5.0.5
- **Droid**：新增调度工具（`ccb_ask_*` 与 `cask/gask/lask/oask`），并提供 `ccb droid setup-delegation` 安装命令

### v5.0.4
- **OpenCode**：修复 `-r` 恢复在多项目切换后失效的问题

### v5.0.3
- **守护进程**：全新的稳定守护进程设计

### v5.0.1
- **技能更新**：新增 `/all-plan`（Superpowers 头脑风暴 + 可用性分发）；Codex 侧新增 `lping/lpend`；`gask` 在 `CCB_DONE` 场景保留简要执行摘要。
- **状态栏**：从 `.autoflow/roles.json` 读取角色名（支持 `_meta.name`），并按路径缓存。
- **安装器**：安装技能时复制子目录（如 `references/`）。
- **CLI**：新增 `ccb uninstall` / `ccb reinstall`，并清理 Claude 配置。
- **路由**：项目/会话解析更严格（优先 `.ccb`，避免跨项目 Claude 会话）。

### v5.0.0
- **解除依赖**：无需先启动 Claude，Codex 也可以作为主 CLI
- **统一控制**：单一入口控制 Claude/OpenCode/Gemini
- **启动简化**：移除 `ccb up`，默认 `ccb.config` 自动生成
- **挂载更自由**：更灵活的 pane 挂载与会话绑定
- **项目 askd 自启**：项目 askd 与 provider runtime 会在项目 tmux namespace 中按需启动
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
- **智能运行队列**: 项目 askd 提供 60 秒空闲超时与 provider 队列能力
- **跨 AI 协作**: 支持多个 Agent (Claude/Codex) 同时调用同一个 Agent (OpenCode)
- **打断检测**: Gemini 现在支持智能打断处理
- **链式执行**: Codex 可以调用 `oask` 驱动 OpenCode
- **稳定性**: 健壮的队列管理和锁文件机制
