# Agent-First V2 Architecture

> 历史说明：本文包含早期双后端与 `askd` 时代的设计上下文，不应作为当前 runtime backend 权威来源。当前主仓已收口为 tmux-only；原生 Windows 后续请以 `docs/ccbd-windows-psmux-plan.md` 为准。

## 1. 目标与边界

本方案是一次彻底的 v2 重构，目标是把 CCB 从 provider-first 改为 agent-first。

核心目标：

- 用户操作的第一身份是 `agent_name`，不是 `provider`。
- 同一项目下允许并发启动多个同类 CLI，但必须做到会话隔离、工作区隔离、状态隔离。
- `ccb` 默认动词就是“启动/附着 agent”，不再引入 `up` 之类的中间层命令。
- 所有异步通信、会话恢复、权限策略都以 agent 为中心建模。
- 守护进程统一为每项目一个 `askd`，不再为每个 provider 各自维护一套守护模型。
- 设计优先考虑清晰性、稳定性、可扩展性；旧实现的代码兼容性不作为目标。

v2 第一阶段范围：

- agent-first 启动、恢复、停止、投递、观测
- 项目级 `askd`
- 工作区隔离与并发控制
- provider adapter 重构
- tmux / WezTerm 运行时保留

v2 第一阶段不覆盖：

- `maild` 邮件网关重构
- 安装器 / 升级器 / 卸载器重构
- 旧 skills 命令面的完全迁移
- 旧 provider 独立脚本的兼容包装

非目标：

- 不保证旧的 provider-first 内部代码结构可复用。
- 不要求保留旧的 `provider:instance` 身份模型。
- 不要求保留旧的多守护拆分架构。
- 不要求继续围绕 `.codex-session`、`.claude-session` 等 provider 根会话文件组织系统。
- 不要求保留旧版 `ask <provider>` / `pend <provider>` / `ccb-ping <provider>` 的命令兼容层。

## 2. 核心原则

### 2.1 Agent 是一级实体

系统中的所有核心操作都以 agent 为单位：

- 启动
- 附着
- 停止
- 恢复
- 提问
- 查看状态
- 查看日志

`provider` 只作为 agent 的一个属性存在，不直接暴露为运行时主身份。

### 2.2 名称驱动而非类型驱动

用户使用自定义名字访问 agent：

- `ccb agent1 agent2 -r -a`
- `ccb ask agent1 from agent2 "..."`
- `ccb kill`

内部传递统一使用 `agent_name`，而不是 `codex` / `claude` / `gemini` 之类 provider 名。

### 2.3 单项目单守护

每个项目仅维护一个 `askd`：

- 统一接受 CLI 请求
- 统一调度 agent runtime
- 统一维护 job store / event store / health state
- 统一管理 provider adapter

这样可以避免多守护之间的状态分裂、竞争写入和恢复语义不一致。

### 2.4 并发必须伴随隔离

“允许多个同类 CLI 并发”不能只靠更换 session 文件名实现，必须同时隔离：

- agent 控制目录
- provider runtime 元数据
- 真实工作目录
- provider 对话绑定
- 日志与事件流
- 锁与 pid

没有隔离的并发，本质上只是把冲突延后。

## 3. CLI 总体设计

### 3.1 默认入口

默认入口为：

```bash
ccb [agent_names...] [-r] [-a]
```

示例：

```bash
ccb
ccb agent1
ccb agent1 agent2 -r -a
```

语义：

- 无参数：启动或附着配置中的默认 agents
- 指定 `agent_names`：启动或附着指定 agent
- `-r`：对目标 agent 应用恢复策略
- `-a`：对目标 agent 应用自动权限策略

不再设计：

```bash
ccb up agent1 agent2
```

原因：

- `ccb` 默认动作已经是“启动/附着 agent”
- 再加 `up` 只会增加解析复杂度和用户心智负担

### 3.2 管理命令与投递命令

`ccb` 统一承载 agent 生命周期、消息投递与诊断命令：

```bash
ccb ask <target> [from <sender>] <message>
ccb cancel <job_id>
ccb kill
ccb kill -f
ccb ps
ccb ps --alive
ccb ping <agent_name|all>
ccb watch <agent_name|job_id>
ccb pend <agent_name|job_id> [N]
ccb logs <agent_name>
ccb doctor
ccb config validate
```

简单形式：

```bash
ccb ask <target> [from <sender>] <message>
```

扩展形式：

```bash
ccb ask [options...] <target> [from <sender>] -- <message...>
```

示例：

```bash
ccb ask agent1 "请整理当前状态"
ccb ask agent1 from agent2 "我已经完成 schema 设计，你继续实现"
ccb ask all from system "准备进入统一回归测试"
```

补充约定：

- `kill` 表示显式终止当前项目全部 agent runtime，并卸载当前项目 askd
- 不提供单 agent 的 `stop` / `kill`
- `kill -f` 用于清理孤儿进程、陈旧 socket、失效 pane 等全局脏状态
- 若单个 agent 出现异常，处理方式是 `ccb kill` 后重新按目标 agent 集合拉起

### 3.3 `ccb ask` 消息语义

`ccb ask` 至少需要两个核心字段：

- `target`
- `message`

可选字段：

- `from`

设计规则：

- 简单形式固定为 `ccb ask <target> [from <sender>] <message>`
- 扩展形式固定为 `ccb ask [options...] <target> [from <sender>] -- <message...>`
- 省略 `from` 时，sender 从当前 workspace binding 自动推断；推断失败则回退为 `user`
- `from` 出现时仍是固定位置的语法关键字
- `sender` 允许三类值：`user`、`system`、`<agent_name>`
- `<target>` 允许两类值：`<agent_name>`、`all`
- `all` 为保留目标名，不能作为 agent 名
- `from` 为保留关键字，不能作为 agent 名
- `user` 与 `system` 为保留 actor id，不能作为 agent 名
- `all` 只广播给当前存活的 agents，不隐式拉起离线 agent
- 当 `sender` 是某个在线 agent 时，广播必须排除发送者自身
- 广播投递应采用“逐个 agent 独立入队”，不能把一条 job 共享给多个 agent
- 若 `sender` 是 agent 名，askd 必须校验该 agent 是否存在；是否要求其在线可由策略决定

命令解析规则：

- 简单形式下：
  - 第 1 个位置参数解析为 `target`
  - 第 2 个位置参数必须字面等于 `from`
  - 第 3 个位置参数解析为 `sender`
  - 第 4 个及之后的位置参数合并为空格连接的 `message`
- 扩展形式下：
  - 先解析前置 options
  - 第 1 个位置参数解析为 `target`
  - 第 2 个位置参数必须字面等于 `from`
  - 第 3 个位置参数解析为 `sender`
  - `--` 之后全部参数合并为空格连接的 `message`
- `message` 不能为空字符串

示例解析：

```bash
ccb ask agent1 from agent2 继续实现 schema
```

等价于：

- `target = "agent1"`
- `sender = "agent2"`
- `message = "继续实现 schema"`

因此下面两种写法都应成立：

```bash
ccb ask agent1 from agent2 继续实现 schema
ccb ask agent1 from agent2 "继续实现 schema"
ccb ask --task-id t1 agent1 from agent2 -- 继续实现 schema
```

后续如果要扩展参数，统一放在前置 options 区，并使用 `--` 与消息正文分隔，例如：

- `--task-id`
- `--reply-to`
- `--mode`

### 3.4 保留关键字

以下词保留为命令关键字或系统 actor，不允许作为 agent 名：

- `all`
- `from`
- `user`
- `system`
- `ask`
- `cancel`
- `pend`
- `ping`
- `watch`
- `kill`
- `ps`
- `logs`
- `doctor`
- `config`
- `version`
- `update`
- `help`

建议 agent 命名规则：

- 正则：`^[a-zA-Z][a-zA-Z0-9_-]{0,31}$`
- agent 名统一按小写规范化存储，大小写不敏感
- `Agent1` 与 `agent1` 视为同名冲突
- 配置加载阶段即进行冲突校验

### 3.5 项目解析规则

`ccb` 与 `ccb ask` 都必须先解析“当前操作属于哪个项目”，再决定要连接哪个 `askd`。

建议解析顺序：

1. 若显式提供 `--project <path>`，以该路径为准
2. 否则从当前工作目录向上查找最近的 `.ccb/`
3. 若当前目录位于某个已注册 agent workspace 内，则回溯到该 workspace 绑定的 target project
4. 若以上都失败，则报错，不隐式创建新项目

补充规则：

- `all` 广播永远是“当前项目内的 all”，不能跨项目广播
- `ccb ask` 从错误项目目录执行时，必须失败而不是把消息投递到错误项目
- `ccb doctor` 必须输出项目解析结果，便于排障

## 4. 配置模型

### 4.1 配置文件位置

v2 仍沿用项目级配置入口：

- 项目：`.ccb/ccb.config`
- 全局：`~/.ccb/ccb.config`

但其外部 schema 改为单一的紧凑 agent-first 配置，不再以 provider 列表或字段表作为外部模型。

格式约束：

- v2 中 `ccb.config` 只接受紧凑文本格式
- 每个 agent 项必须写成 `agent_name:provider`
- 多个条目可用逗号或换行分隔，`#` 后内容视为注释
- `cmd` 是独立保留 token，只表示 shell pane，不是 agent
- `ccb config validate` 必须给出精确 token 级报错

### 4.2 推荐配置结构

推荐写法：

```text
writer:codex,reviewer:claude
```

带 cmd pane 的示例：

```text
agent1:codex,agent2:codex,agent3:claude,cmd
```

### 4.3 默认 agent

当配置不存在时，系统自动生成最小默认配置：

```text
codex:codex,claude:claude
```

### 4.4 配置字段

当前外部配置文件不再暴露字段表。每个 `agent_name:provider` 项都会在加载时展开为固定配置：

- `provider`：取自条目右侧 provider
- `target = "."`
- `workspace_mode = "git-worktree"`
- `restore = "auto"`
- `permission = "manual"`

其他运行时字段保持内部默认值，由统一的 `ProjectConfig` / `AgentSpec` 模型承接。

### 4.5 配置命名归一化

命名归一化规则收敛为：

- agent 名大小写不敏感，加载后统一规范化为小写
- 规范化后重名直接报错
- `cmd` 不能作为 agent 名，因为它是独立 pane 保留字

## 5. 目录与状态布局

### 5.1 Agent 控制目录

每个项目在 `.ccb/agents/<agent_name>/` 下维护 agent 控制目录：

```text
.ccb/
  ccb.config
  askd/
    lease.json
    askd.sock
  agents/
    agent1/
      agent.json
      runtime.json
      provider.json
      restore.json
      jobs.jsonl
      events.jsonl
      logs/
    agent2/
      ...
```

这里存放的是 CCB 自己的状态，不等同于 provider 的真实工作目录。

#### 5.1.1 `askd/` 运行时目录决议

项目级守护运行时目录统一固定为：

- `.ccb/askd/`

不得再引入并列的 `.ccb/run/` 作为 askd 主路径。

最小固定文件如下：

- `.ccb/askd/lease.json`
- `.ccb/askd/askd.sock`

约束：

- `socket_path` 在文档、代码、诊断输出中统一写为 `.ccb/askd/askd.sock`
- `lease` 的权威落盘路径统一写为 `.ccb/askd/lease.json`
- 若历史实现曾使用 `.ccb/run/`，仅允许在迁移工具或兼容清理逻辑中提及，不得继续作为 v2 主路径

### 5.2 真实工作目录

真实工作目录与 agent 控制目录分离。

推荐优先级：

1. `git-worktree`
2. `copy`
3. `inplace`

默认推荐 `git-worktree`。

原因：

- 大多数 CLI 的对话恢复都和实际 cwd 强绑定
- 只有独立 cwd，多个同类 provider 才能真正并发
- 文件修改、索引缓存、临时文件、provider session 才不会互相污染

### 5.3 工作区设计

对于 git 项目：

- agent 控制目录：`.ccb/agents/<agent_name>/`
- agent 真实工作区：独立 git worktree
- agent 的 provider 进程实际在该 worktree 下运行

对于非 git 项目：

- 可退化到 `copy` 或 `inplace`
- 但 `inplace` 仅作为明确选择，不作为默认模式

#### 5.3.1 工作区路径规则

工作区路径必须可预测、可重建、可清理，不能依赖隐式临时路径。

建议默认布局：

```text
.ccb/
  workspaces/
    agent1/
    agent2/
```

若配置指定 `workspace_root`，则布局为：

```text
<workspace_root>/
  <project_slug>/
    <agent_name>/
```

路径规则建议：

- `project_slug`
  - 由项目根路径稳定派生
  - 只允许 `[a-z0-9._-]`
- `agent_name`
  - 使用规范化后的 agent 名
- worktree/copy/inplace 三种模式都必须能反推出其 `target_project`

禁止：

- 每次启动随机生成工作区目录
- 依赖系统临时目录但不落盘引用
- 让 `workspace_root` 与 `.ccb/agents/` 失去映射关系

#### 5.3.2 `git-worktree` 分支命名规则

`git-worktree` 模式下必须显式定义分支命名规则，避免后续实现时各写各的命名逻辑。

建议默认：

- `branch_template = "ccb/{agent_name}"`

若用户自定义 `branch_template`，仅允许使用以下变量：

- `{agent_name}`
- `{project_slug}`
- `{date}`

建议分支命名约束：

- 默认复用同一个 agent branch，而不是每次 ask 新建分支
- branch 名必须稳定映射到 agent
- `doctor` 必须能显示 `base_commit`、`head_commit`、`branch_name`

若检测到以下情况：

- worktree 丢失
- branch 被删除
- branch 指向异常提交

则恢复逻辑必须进入显式 repair/fresh 分支，而不是悄悄创建新 branch 掩盖问题。

#### 5.3.3 `copy` / `inplace` 模式规则

`copy` 模式：

- 只适用于非 git 项目，或用户显式接受复制成本的场景
- 必须记录 `source_root` 与 `workspace_path`
- 必须定义 refresh 策略：
  - `never`
  - `on-start`
  - `manual`

默认建议：

- `copy.refresh = on-start`

`inplace` 模式：

- 明确表示多个 agent 共享同一真实工作目录
- 默认不允许两个 `inplace` agent 同时在线
- 若用户显式允许，系统也必须把该项目标记为 `unsafe_shared_workspace = true`

这样可以避免用户误以为 `inplace` 也具备和 `git-worktree` 一样的隔离性。

#### 5.3.4 工作区清理与回收

工作区回收规则也需要在 v2 中固定：

- `ccb kill`
  - 默认不删 workspace，只卸载 askd
- 显式清理命令保留如下：
  - `ccb workspace gc`
  - `ccb workspace prune`

命令语义必须固定：

- `ccb workspace gc`
  - 只扫描“可安全删除”的候选对象
  - 默认输出候选清单，不直接删除
  - 只有显式 `--apply` 时才执行删除
- `ccb workspace prune <agent_name>...`
  - 只针对指定 agent 的 workspace 做显式裁剪
  - 若该 agent 仍在线、仍被 askd 绑定，必须拒绝执行
- `ccb workspace prune --deleted-agents`
  - 只清理配置中已经不存在的 agent 对应工作区

workspace 元数据必须至少持久化：

- `project_id`
- `agent_name`
- `workspace_mode`
- `workspace_path`
- `pinned`
- `dirty`
- `last_bound_at`
- `last_runtime_ref`

允许自动清理的对象：

- 已失联且无绑定 agent 的 worktree
- 已被删除 agent 配置的孤儿 workspace
- 与当前 project_id 不匹配的陈旧 workspace

不允许自动清理的对象：

- 仍有未审计修改的 workspace
- 仍被 runtime 绑定的 workspace
- 用户显式 pinned 的 workspace

执行约束：

- `gc` 与 `prune` 都必须先读取 workspace 元数据，而不是只靠文件名推断
- `gc --apply` 删除前必须再次校验 runtime 绑定关系，避免并发删除
- 若是 git workspace，必须检查 `git status --porcelain`
- 若是 non-git workspace，必须依赖显式 dirty 标记或内容快照校验
- pinned workspace 只能通过显式 unpin 后再删除
- 对删除动作必须写审计事件，至少记录 `who / when / workspace_path / reason`

### 5.4 为什么不能只在 `.ccb/` 下伪造 cwd

仅在 `.ccb/` 里放一个 agent 子目录，再通过 prompt 告诉模型“真实目录其实在别处”，并不能可靠解决并发问题。

原因：

- provider 的 resume 逻辑通常基于真实 cwd 或其派生索引
- provider 自己写出的缓存、索引、session 元数据仍会绑定运行时 cwd
- 文件工具相对路径、`git` 行为、编辑器集成都依赖真实 cwd
- 会出现“对话恢复在 A，文件操作在 B”的语义撕裂

因此 v2 采用“控制目录 + 真实独立工作区”双层模型。

### 5.5 运行时后端模型

当前项目的大量稳定性来自真实终端会话、pane 绑定、TTY 行为与可见运行态，因此 v2 必须显式保留运行时后端模型。

定义三类 runtime mode：

- `pane-backed`：运行在 tmux / WezTerm pane 内，可见、可附着、适合强交互 provider
- `pty-backed`：运行在受控 PTY 内，不要求独立 pane，但仍保留 TTY 语义
- `headless`：纯后台进程，无可见 pane，仅适用于明确支持的 provider

v2 第一阶段建议：

- 默认 `runtime_mode = pane-backed`
- `pty-backed` 仅对验证稳定的 provider 开放
- `headless` 不作为第一阶段主路径
- 但允许在少数 provider 上先落地 headless completion path，用于验证 `structured_result_detector`

补充要求：

- runtime mode 由 agent 配置决定，而不是由 provider 名硬编码
- tmux / WezTerm 仅作为 pane backend 的实现，不应污染 agent/core 数据模型
- pane 标题、布局、当前 pane 锚定仍属于 v2 保留能力，而不是被视为旧功能遗留

## 6. Agent 生命周期模型

### 6.1 状态机

每个 agent 维护独立状态机：

- `stopped`
- `starting`
- `running`
- `degraded`
- `restoring`
- `failed`
- `stopping`

### 6.2 启动流程

`ccb agent1 agent2 -r -a` 的处理流程：

1. 解析目标 agent 列表
2. 读取并校验配置
3. 为每个 agent 计算最终策略
4. 确保 agent 控制目录存在
5. 确保真实工作区存在
6. 连接或启动项目级 `askd`
7. 对每个 agent 执行 attach / restore / start 判定
8. 注册 runtime 与 event stream

### 6.3 单 agent 幂等启动

对同一个 `agent_name`：

- 如果已在线，则默认 attach
- 如果未在线，则恢复或重启
- 不允许同名 agent 重复创建第二个 runtime

这样“并发”是通过多个不同 agent 名实现，而不是同名多实例竞争。

### 6.4 单 agent 调度策略

当前项目通过 provider daemon 排队来避免上下文污染。v2 需要把这个能力上升为 agent 级默认规则。

默认策略：

- `queue_policy = serial-per-agent`
- 同一 agent 任意时刻只允许一个 active conversational job
- 新 job 按 FIFO 进入该 agent 自己的队列
- 广播 fan-out 后，每个目标 agent 仍走各自独立 FIFO 队列

可选策略：

- `serial-per-agent`
- `reject-when-busy`
- `interruptible`

第一阶段建议只实现：

- `serial-per-agent`
- `reject-when-busy`

不建议第一阶段就开放默认可中断，因为这会放大 provider 恢复与状态一致性问题。

## 7. `-r` 恢复模型

### 7.1 `-r` 的新语义

在 agent-first 架构里，`-r` 恢复的是 agent 连续性，而不是简单恢复某个 provider 的最近会话。

`-r` 对单个 agent 的恢复优先级：

1. attach 已在线 runtime
2. 恢复该 agent 绑定的 provider 会话
3. 恢复该 agent 的 CCB checkpoint / summary / task state
4. fresh start

因此 `-r` 的本质是：

- 先恢复 agent 身份
- 再利用 provider 能力
- provider 恢复失败不应直接导致 agent 身份丢失

### 7.2 内部恢复模式

CLI 可以继续暴露简单的 `-r`，但内部不再使用布尔值，而是统一成：

- `attach`
- `provider`
- `memory`
- `fresh`
- `auto`

其中：

- `-r` 等价于 `restore=auto`
- `auto = attach -> provider -> memory -> fresh`

### 7.3 为什么不能只恢复 provider session

如果只恢复 provider session，会出现几个问题：

- provider session 失效后，整个 agent 语义断裂
- agent 的任务上下文、待办、修改范围、工作区分支信息无法恢复
- 不同 provider 的恢复能力不一致，导致系统语义不统一

因此 v2 需要单独维护 agent 级 checkpoint。

### 7.4 Agent 级恢复元数据

每个 agent 至少保存：

- `agent_name`
- `provider`
- `target_project`
- `workspace_path`
- `workspace_mode`
- `provider_session_ref`
- `provider_runtime_ref`
- `last_checkpoint`
- `conversation_summary`
- `open_tasks`
- `files_touched`
- `base_commit`
- `head_commit`
- `last_successful_restore`
- `last_seen_at`

### 7.5 `-r` 的判定逻辑

对于 `ccb agent1 -r`：

- 若 `agent1` 已在线，直接附着
- 若在线 runtime 不存在，但 `provider_session_ref` 仍有效，则恢复 provider 对话
- 若 provider 无法恢复，则注入 `conversation_summary + open_tasks + workspace metadata`
- 若控制目录或工作区损坏，则标记 `restore_failed` 并 fresh start

### 7.6 `ccb ask` 对恢复状态的要求

单播消息示例：

```bash
ccb ask agent1 from user "..."
```

广播消息示例：

```bash
ccb ask all from system "..."
```

askd 会自行解析：

- agent 是否在线
- 是否需要懒恢复
- 是否需要等待 runtime ready
- 是否存在未完成 job

单播调用方不需要知道底层是 attach、provider-resume 还是 checkpoint-resume。

广播额外规则：

- `all` 默认只发给 `running` 或 `degraded` 状态的 agent
- 广播不触发离线 agent 自动恢复，避免一次广播把整个项目全部拉起
- 若发送者是某个 agent，广播必须排除该发送者自身
- 广播结果需要返回逐 agent 投递状态，而不是仅返回一个聚合成功/失败

### 7.7 History Snapshot 与 Handoff 产物

当前项目已经具备 `./.ccb/history/`、会话切换导出与 handoff 审计能力。v2 不应丢掉这些资产，而应把它们纳入标准恢复模型。

每个项目保留：

- 结构化恢复状态：供 askd 和 adapter 自动恢复
- 人类可审计 snapshot：供人工阅读、handoff、故障排查

建议目录：

```text
.ccb/
  history/
    agent1-20260317-120000-checkpoint.md
    agent2-20260317-121500-switch.md
```

建议触发时机：

- provider session 切换
- agent 显式停止
- restore 失败回退到 memory 模式前
- 用户显式执行 handoff / snapshot 命令

每份 snapshot 至少包含：

- `agent_name`
- `provider`
- `workspace_path`
- `provider_session_ref`
- `conversation_summary`
- `open_tasks`
- `files_touched`
- `base_commit`
- `head_commit`
- `created_at`

这样可以同时满足机器恢复和人工审计，不再把所有恢复语义都绑死在 provider 私有日志里。

## 8. `-a` 权限模型

### 8.1 `-a` 的新语义

`-a` 不再表示“某个 provider 的特殊全自动开关”，而是统一表示：

- `permission=auto`

CLI 暴露仍可保留 `-a`，但内部统一映射到权限策略枚举。

### 8.2 权限模式

统一定义：

- `manual`
- `auto`
- `readonly`

建议默认值：

- 配置默认 `manual`
- CLI `-a` 覆盖为 `auto`

### 8.3 Provider 适配规则

`askd` 只认统一权限语义，再由 provider adapter 转换：

- Claude adapter 转换为 Claude 所需启动参数
- Codex adapter 转换为 Codex 所需启动参数
- 其他 provider 采用各自实现

### 8.4 禁止修改用户全局配置

v2 明确禁止为了实现 `-a` 去修改用户全局配置，例如：

- `~/.codex/config.toml`
- `~/.claude/...`
- 其他 provider 全局用户配置

原因：

- 并发 agent 下会互相污染
- 一个 agent 的权限策略不应影响另一个 agent
- 项目级行为不应偷偷改写用户全局环境

正确做法：

- 通过启动参数注入
- 通过进程级环境变量注入
- 通过 askd 临时 overlay 注入

### 8.5 `-a` 与 `-r` 的叠加

`ccb agent1 -r -a` 的含义是：

- 恢复 `agent1`
- 恢复后按 `permission=auto` 启动或附着

如果 attach 到一个已在线 runtime：

- 默认不强行热切换已启动进程的权限策略
- 仅对新建 runtime 生效
- 若需要强制重启并套用权限策略，应通过显式命令实现

## 9. Provider 插件模型

### 9.1 Provider 不是核心身份，只是适配器

每个 provider adapter 负责：

- 进程启动
- 健康检查
- 发送消息
- 读取输出
- 解析 provider session 引用
- 恢复 provider 会话
- 应用权限策略

### 9.2 Provider 适配接口

统一接口建议：

- `prepare(agent_spec, runtime_spec)`
- `start(agent_spec, launch_spec)`
- `attach(runtime_ref)`
- `health(runtime_ref)`
- `submit(message, runtime_ref)`
- `watch(runtime_ref, cursor)`
- `restore(agent_state)`
- `shutdown(runtime_ref)`

### 9.3 Provider manifest

每个 provider 通过 manifest 声明能力：

- `supports_resume`
- `supports_permission_auto`
- `supports_stream_watch`
- `supports_subagents`
- `supports_workspace_attach`

askd 基于 capability，而不是硬编码 provider 名称做分支。

阶段化落地建议：

- 目标形态仍然是 `providers/` 目录下的 manifest / catalog / adapter 分层
- 但在阶段 2，为降低重构风险，允许先以独立核心文件落地 catalog 骨架，例如：
  - `lib/provider_models.py`
  - `lib/provider_catalog.py`
- 待阶段 4 provider adapter 迁移稳定后，再整体并入目标 `providers/` 目录结构
- 这种过渡只影响代码组织，不改变对外的 manifest / capability / completion profile 语义

### 9.3.1 完成检测必须独立于 provider adapter

v2 中必须把“完成检测”从 provider adapter 中抽离出来，形成独立子系统。

原因：

- provider adapter 负责“怎么启动、怎么发送、怎么附着”
- completion detector 负责“什么时候这一轮真的结束了”
- reply selector 负责“终态成立后，最终回复文本选哪一条”

如果继续把这三件事混在一起，会出现几个问题：

- 每个 provider 都会重复实现一套状态机
- transport 改动会污染完成判定逻辑
- 很难把 exact / observed / degraded 三种完成语义统一暴露给 askd
- 测试会退回到“跑真 CLI 看最终文本”这种不稳定路径

因此建议 askd 内部显式拆成三层：

- `provider adapter`
- `event/session source`
- `completion detector`

职责边界：

- `provider adapter`：启动 runtime、发送请求、健康检查、恢复 session、取消请求
- `event/session source`：把 provider 私有输出规范化为统一事件或快照
- `completion detector`：消费统一事件/快照，输出 terminal decision

### 9.3.1.1 Execution Runtime Context

当 askd 进入 execution/polling 阶段后，provider adapter 不应再反向查询 askd 内部状态。

建议由 dispatcher 在 `job_started` 时一次性下发 `ProviderRuntimeContext`，至少包含：

- `agent_name`
- `workspace_path`
- `backend_type`
- `provider_runtime_ref`
- `provider_session_ref`
- `runtime_pid`
- `runtime_health`

约束：

- adapter 只能依赖这份 runtime context 和自身 submission state
- adapter 不应直接 import askd registry / runtime service 再二次查询
- 若 runtime context 不足以驱动真实 provider，应返回“被动模式”而不是硬失败
- “被动模式”表示：
  - 不产出 terminal
  - 不破坏现有队列/取消语义
  - 等 start/attach 链路补齐真实 session 信息后再自然激活

这样可以保证：

- fake provider 与真实 provider 共用同一 execution 接口
- execution 层边界清晰，不会退回 askd 巨石
- 真实 provider 可以按 session 完整度逐步接入，而不必一次性改穿所有链路

### 9.3.2 统一完成检测接口

建议定义统一接口如下：

- `CompletionSource.capture_baseline()`
- `CompletionSource.poll(cursor, timeout)`
- `CompletionDetector.bind(request_context, baseline)`
- `CompletionDetector.ingest(item)`
- `CompletionDetector.decision()`
- `ReplySelector.select(decision, buffered_items)`

建议统一数据模型：

- `CompletionItem`
  - `kind`
  - `timestamp`
  - `cursor`
  - `payload`
- `CompletionDecision`
  - `status`
  - `reason`
  - `confidence`
  - `reply`
  - `anchor_seen`
  - `reply_started`
  - `reply_stable`
  - `provider_turn_ref`
  - `source_cursor`
- `RequestContext`
  - `req_id`
  - `agent_name`
  - `provider`
  - `timeout_s`
  - `compatibility_mode`
  - `anchor_text`

统一循环建议为：

```text
adapter.submit(req):
  runtime = ensure_runtime()
  source = build_completion_source(runtime, req)
  detector = build_completion_detector(runtime, req)
  selector = build_reply_selector(runtime, req)

  baseline = source.capture_baseline()
  detector.bind(req, baseline)
  send(req)

  while before deadline:
    item = source.poll(cursor, timeout_step)
    if item is None:
      if detector.decision().terminal:
        break
      continue

    detector.ingest(item)
    if detector.decision().terminal:
      break

  decision = detector.decision()
  decision.reply = selector.select(decision)
  return decision
```

关键原则：

- adapter 不能自己直接宣布 `completed`
- 必须由 detector 输出 terminal decision
- selector 只在终态成立后选 reply，不参与完成判定
- 所有 provider 最终都返回同一套 `CompletionDecision`

### 9.3.3 检测器族划分

不应按 provider 名称写死 detector，而应按“终态可观测类型”分族。

建议至少定义以下 detector family：

- `protocol_turn_detector`
  - 适合存在明确 turn terminal event 的 provider
- `structured_result_detector`
  - 适合存在最终 `result` / `final` 结构化结果事件的 provider
- `session_boundary_detector`
  - 适合存在强观测 session 边界的 provider
- `anchored_session_stability_detector`
  - 适合只有会话快照、没有公开终态协议的 provider
- `legacy_text_quiet_detector`
  - 仅用于 compatibility mode 的降级兜底

各 detector 的职责：

- `protocol_turn_detector`
  - 等待明确协议事件，如 `task_complete`
- `structured_result_detector`
  - 等待结构化结果事件，如 `result`
- `session_boundary_detector`
  - 根据强观测日志边界判定，如 `assistant -> turn_duration`
- `anchored_session_stability_detector`
  - 根据 anchor 后 reply 收敛判定，如 `session_reply_stable`
- `legacy_text_quiet_detector`
  - 仅在显式兼容模式下，基于 quiet window 做 degraded completion

必须明确：

- `legacy_text_quiet_detector` 不能成为默认 detector
- 一个 provider 可以有多个 detector profile
- 最终选择哪个 detector，取决于该 runtime 运行模式，而不是 provider 名称本身
- 对尚未完成结构化迁移的 provider，允许暂时以 `legacy_text_quiet_detector` 作为过渡 profile
- 该过渡 profile 必须显式标记为 `legacy`，不能伪装成 exact / observed 主路径

### 9.3.4 Provider completion profile

除了基础 capability，provider manifest 还应显式声明 completion profile。

provider manifest 必须包含：

- `completion_family`
- `completion_source_kind`
- `supports_exact_completion`
- `supports_observed_completion`
- `supports_anchor_binding`
- `supports_reply_stability`
- `supports_terminal_reason`
- `supports_legacy_quiet_fallback`

`completion_source_kind` 必须限制在以下枚举中：

- `protocol_event_stream`
- `structured_result_stream`
- `session_event_log`
- `session_snapshot`
- `terminal_text`

`completion_family` 必须限制在以下枚举中：

- `protocol_turn`
- `structured_result`
- `session_boundary`
- `anchored_session_stability`
- `legacy_text_quiet`

这样 askd 可以按 runtime profile 选择 detector：

- 不是 `if provider == codex`
- 而是 `if completion_family == protocol_turn`

#### 9.3.4.1 Compatibility Mode 定义

`compatibility_mode` 是 completion 子系统的运行策略开关，必须单独定义清楚。

它不负责：

- workspace 选择
- runtime backend 选择
- provider 启动参数
- 权限模型

它只负责：

- 是否允许 legacy done marker
- 是否允许 quiet fallback
- legacy detector 是不是主路径

建议取值：

- `strict`
  - 禁止 legacy marker 与 quiet fallback
- `allow-fallback`
  - 新 detector 为主路径，仅在 profile 允许时启用 degraded fallback
- `legacy-primary`
  - 以 `legacy_text_quiet_detector` 为主路径

作用域与解析顺序：

1. 运行时显式覆盖
2. agent 配置中的 `compatibility_mode`
3. provider completion profile 默认值

建议默认：

- `Codex`
  - `strict`
- `Claude`
  - `strict`
- `Gemini`
  - `strict`
- `OpenCode / Droid / 其他 legacy provider`
  - `legacy-primary`

约束：

- `strict` 下不得触发 `legacy_done_marker` 或 `legacy_quiet`
- `allow-fallback` 下只有在 `supports_legacy_quiet_fallback = true` 时才可退化
- `legacy-primary` 必须把 `completion_confidence` 固定为 `degraded`
- `doctor` 必须显示 agent 的 `effective_compatibility_mode`

### 9.3.5 Provider 到 detector 的映射

当前阶段建议映射如下：

- `Codex`
  - `protocol_turn_detector`
- `Claude headless`
  - `structured_result_detector`
- `Claude interactive`
  - `session_boundary_detector`
- `Gemini structured`
  - `structured_result_detector` 或 `protocol_turn_detector`
- `Gemini pane-backed`
  - `anchored_session_stability_detector`
- `OpenCode`
  - 暂时保留 `legacy_text_quiet_detector`
- `Droid`
  - 暂时保留 `legacy_text_quiet_detector`
- 其他尚未优化的 provider
  - 暂时保留 `legacy_text_quiet_detector`

这个映射说明两个原则：

- 同一个 provider 在不同运行模式下可以绑定不同 detector
- detector family 是可扩展的，未来新增 provider 不必复制旧状态机

### 9.3.6 Legacy provider 过渡策略

不是所有 provider 都要在第一阶段完成结构化结束检测改造。

对于当前还没有稳定公开终态事件、或暂时不准备优先重构的 provider，例如：

- `OpenCode`
- `Droid`
- 其他低优先级 provider

允许继续沿用当前 `CCB_DONE + quiet window` 的老路径，但必须满足以下约束：

- 只能挂到 `legacy_text_quiet_detector`
- `completion_confidence` 必须固定为 `degraded`
- `completion_reason` 必须明确标记为 `legacy_quiet` 或 `legacy_done_marker`
- `CCB_DONE` 缺失时不得冒充 exact 完成，只能在显式兼容模式下接受 quiet fallback
- `doctor` / `ping` / `ps` 必须能显示该 agent 当前运行在 `legacy completion mode`

这意味着：

- v2 架构允许“核心框架先抽象，provider 分批迁移”
- 没有优化过的 provider 仍然可以继续工作
- 但文档和运行时必须把它们和 `Codex` / `Claude` / `Gemini` 的新检测路径明确区分

建议迁移优先级：

1. `Codex`
2. `Claude`
3. `Gemini`
4. `OpenCode`
5. `Droid` 与其他 provider

这样可以先把高价值、可观测性更强的 provider 做干净，再逐步收缩 legacy 覆盖范围。

### 9.4 Codex 完成识别规范

v2 中 `Codex` adapter 不应再把 prompt 级 `CCB_DONE` 当作主完成信号。

基于 Codex 开源实现，真正可靠的 turn 终态信号是协议事件：

- `task_started` / `turn_started`
- `task_complete` / `turn_complete`
- `turn_aborted`

其中：

- `task_complete` 表示一整轮 agent turn 已完成，而不只是一次模型流结束
- `turn_aborted` 表示该 turn 被中断或异常终止
- `final_answer` 仅是 assistant message 的 `phase` 标签，不是完成判据
- `response.completed` 仅代表一次 sampling request 结束，不代表整轮 turn 结束

因此 `Codex` completion policy 必须收敛为：

- `CCB_REQ_ID` 仅用于把本次 ask 锚定到正确 user turn
- `task_complete` 作为 `completed` 的唯一 exact terminal signal
- `turn_aborted` 作为 `cancelled` / `failed` 的 exact terminal signal
- `final_answer` 仅用于选择“最终回复文本”，不参与完成判定
- `CCB_DONE` 退出 Codex 主判定链路，仅可保留为 legacy 调试辅助
- idle timeout 不得再作为正常完成路径，仅可作为显式兼容开关下的降级兜底

建议 Codex adapter 的识别顺序如下：

1. 在发送前记录日志基线
2. 发送带 `CCB_REQ_ID` 的 user prompt
3. 监听 Codex rollout JSONL 中的结构化事件，而不是只监听 assistant 文本
4. 捕获发送后的首个 `task_started`，记为候选 turn
5. 在后续 `user_message` / `response_item(user)` 中确认 `CCB_REQ_ID`，将请求与候选 turn 绑定
6. 等待该 turn 的 `task_complete` 或 `turn_aborted`
7. 若收到 `task_complete`，优先使用事件中的 `last_agent_message` 作为最终 reply
8. 若 `last_agent_message` 缺失，则退回同一 turn 内 `phase=final_answer` 的最后一条 assistant message
9. 若仍缺失，再退回同一 turn 内最后一条 assistant message

必须明确区分两层完成：

- sampling request completion：provider 流完成，可继续 follow-up tool call 或 continuation
- turn completion：Codex 整轮任务结束，才允许 askd 对外发布 terminal result

这意味着：

- 不能因为 assistant 暂时静默而提前认定完成
- 不能因为出现 `final_answer` 文本就提前认定完成
- 不能因为单次 `response.completed` 就对外发布完成
- 必须等 `task_complete`

建议 askd 内部对 Codex 暴露以下 completion 元数据：

- `completion_status = completed | cancelled | failed | incomplete`
- `completion_reason = task_complete | turn_aborted | timeout | pane_dead | legacy_quiet`
- `completion_confidence = exact | degraded`
- `turn_id`
- `anchor_seen`

实现约束：

- `CodexLogReader` 必须升级为结构化事件读取器，至少保留 `payload.type`、`turn_id`、`phase`、`last_agent_message`、`reason`
- 现有“只返回 `(role, text)`”的读取接口不能继续作为 Codex 主路径
- `Codex` adapter 应改为事件驱动状态机，而不是文本尾行匹配状态机
- 若未来存在旧版 Codex 缺少 `task_complete` 事件，必须通过显式 compatibility mode 启用 legacy fallback，而不是默认开启

这套方案的直接收益：

- 与 Codex 官方 turn 生命周期一致
- 避免 `CCB_DONE` 遗忘导致的漏判
- 避免 idle timeout 导致的误判
- 自动覆盖 tool follow-up、stop hook continuation、流重试等复杂路径
- 使 `pend` / `watch` / `doctor` 可以展示更可靠的终态原因

### 9.5 Claude 完成识别规范

`Claude` adapter 的完成识别必须区分两类运行模式：

- headless / SDK mode
- 交互式 pane-backed mode

两者不能复用同一套 completion policy。

#### 9.5.1 Headless / SDK mode

若 `Claude` 以 headless 模式运行，并启用结构化输出：

- `--output-format stream-json`

则应以官方结构化输出中的最终 `result` message 作为 exact completion signal。

在该模式下：

- `result` 到达前，不得视为 completed
- `assistant` message 仅表示中间输出或最终正文片段
- `CCB_DONE` 不应作为主完成信号
- quiet timeout 仅可作为 transport 断裂后的 degraded fallback

因此 headless 模式下的 completion policy 为：

- `result` => `completed`
- 显式错误 / 非零退出 / transport fatal => `failed`
- 用户取消 / askd 取消 => `cancelled`

headless 模式的优势是：

- 直接依赖官方结构化输出
- 不必猜测本地 session log 的语义
- 可获得比交互式模式更清晰的终态边界

#### 9.5.2 交互式 pane-backed mode

若 `Claude` 以长期存活的交互式 pane 运行，并通过 `~/.claude/projects/.../*.jsonl` 观察会话状态，则当前最强的可观测完成边界不是 `CCB_DONE`，而是：

- 最终 `assistant`
- 随后紧邻的 `system.subtype = turn_duration`

在主会话日志中，`turn_duration` 可视为该轮主会话 turn 已收尾的强观测信号。

必须明确：

- `turn_duration` 是强观测信号，不是像 Codex `task_complete` 那样的公开协议契约
- `assistant.message.stop_reason` 不能作为主完成信号，只能作为辅助信号
- `CCB_DONE` 仍然只是 prompt 层 legacy marker
- quiet timeout 只能做 degraded fallback，不应做主完成路径

因此交互式 `Claude` completion policy 必须收敛为：

- `CCB_REQ_ID` 仅用于把本次 ask 锚定到正确 user turn
- 最终 assistant 回复出现后，标记 `reply_started`
- 若主会话出现 `system.turn_duration`，且其 `parentUuid` 指向最后 assistant，则可视为 `completed`
- 若最后 assistant 后仍有 `progress`、subagent 活动或新的 tool 链路，则不得提前判完成
- `stop_reason` 非空时可提升置信度，但 `stop_reason = null` 不得推导为未完成

建议交互式 `Claude` adapter 的识别顺序如下：

1. 在发送前记录主会话日志基线
2. 发送带 `CCB_REQ_ID` 的 user prompt
3. 在主会话中确认带 `CCB_REQ_ID` 的 user anchor
4. 持续跟踪该 anchor 后的 `assistant`、`progress`、`system` 事件
5. 记录最后一条属于本轮的 assistant 文本与其 `uuid`
6. 若出现 `system.turn_duration`，且其 `parentUuid` 等于最后 assistant `uuid`，则视为 exact-like completion
7. 若未出现 `turn_duration`，但 pane 已退出、或 headless mode 返回 `result`、或显式错误到达，则按对应终态处理
8. 仅在 compatibility mode 下，才允许 quiet timeout 作为 degraded completion

#### 9.5.3 Subagent 日志的角色

`Claude` 主会话日志与 `subagents/*.jsonl` 的终态信号不一致。

在 v2 中必须明确：

- subagent 日志默认不作为主完成判定依据
- subagent 日志主要用于活动观测、watch 可视化与“仍在运行”判断
- 若主会话尚未 `turn_duration`，但存在新 subagent / progress 活动，则主会话不得提前 completed
- subagent 最终 `assistant` 可用于辅助展示，但不能单独宣布主任务完成

这意味着：

- 主会话 completion policy 与 subagent activity policy 必须拆开建模
- `supports_subagents` 的 provider 必须暴露“主会话终态”和“子活动存活”两个维度

#### 9.5.4 Claude completion 元数据

建议 askd 内部对 `Claude` 暴露以下 completion 元数据：

- `completion_status = completed | cancelled | failed | incomplete`
- `completion_reason = result_message | turn_duration | api_error | timeout | pane_dead | legacy_quiet`
- `completion_confidence = exact | observed | degraded`
- `anchor_seen`
- `reply_started`
- `last_assistant_uuid`
- `subagent_activity_seen`

其中：

- `exact` 仅用于 headless `result`
- `observed` 用于交互式 `assistant -> turn_duration`
- `degraded` 用于 compatibility fallback

#### 9.5.5 实现约束

- `ClaudeLogReader` 必须升级为结构化事件读取器，不能只抽取 `user` / `assistant` 文本
- 至少要保留 `type`、`subtype`、`uuid`、`parentUuid`、`stop_reason`
- 主会话 reader 与 subagent reader 必须分开建模
- `Claude` adapter 不得再把 `CCB_DONE` 作为唯一完成信号
- 若未来全面迁移到 headless / SDK mode，应优先收敛到 `result` message，而不是继续依赖交互式日志推断

这套方案的直接收益：

- 明确 `Claude` 与 `Codex` 不能共享同一完成状态机
- 交互式模式下比 `CCB_DONE` 更稳
- 避免把 subagent 输出误判成主任务终态
- 为未来 headless 精确完成路径预留更干净的演进方向

### 9.6 Gemini 完成识别规范

`Gemini` adapter 不能简单复用 `Codex` 或 `Claude` 的完成判定逻辑。

基于当前 Gemini CLI 开源实现，可以明确分出三层能力：

- ACP / structured session mode
- headless / non-interactive `stream-json` mode
- 交互式 pane-backed `session-*.json` 观察模式

这三层能力的可观测性强弱差异很大，必须拆开建模。

#### 9.6.1 Structured mode：ACP / non-interactive

若 v2 后续接入 Gemini 的结构化接口，则当前可用的强信号有两类：

- ACP 路径中的 `stopReason = end_turn`
- non-interactive `stream-json` 输出中的最终 `result` event

这两类信号都比读取 `~/.gemini/tmp/.../chats/session-*.json` 更可靠。

因此 structured mode 下的 completion policy 应为：

- `stream-json` 最终 `result` => `completed`
- ACP `stopReason = end_turn` => `completed`
- ACP `stopReason = cancelled` 或等价取消终态 => `cancelled`
- 非零退出、transport fatal、结构化 error => `failed`

其中：

- `agent_message_chunk` 只是中间输出，不是完成信号
- `tool_call` / `tool_call_update(status=completed)` 只表示单个工具阶段完成，不代表整轮 turn 完成
- `CCB_DONE` 不应继续作为 Gemini structured mode 的主完成信号
- quiet timeout 仅可作为 transport 异常后的 degraded fallback

这意味着在 Gemini structured mode 下，应尽量像 `Codex` 一样依赖协议终态，而不是去猜文本何时结束。

#### 9.6.2 交互式 pane-backed `session-*.json` 模式

当前 `ccb` 读取 Gemini 的主路径仍是：

- 发送 prompt 到长期存活的 pane
- 观察 `~/.gemini/tmp/<projectHash>/chats/session-*.json`

但当前 Gemini 会话文件暴露的信息明显偏弱：

- 顶层主要是 `sessionId`、`projectHash`、`startTime`、`lastUpdated`、`messages`
- `messages` 常见只有 `type = user | gemini`
- `gemini` message 常见字段是 `id`、`timestamp`、`content`、`thoughts`、`tokens`、`model`
- 当前落盘会话文件里没有稳定暴露 `stopReason`、`turn_complete`、`result`、`tool lifecycle` 之类终态字段

因此，若继续使用 pane + session file 监控，`Gemini` 无法像 `Codex` 那样获得单一 exact terminal signal。

v2 应明确把该模式定义为：

- 以 anchored reply 为核心的 `observed completion`
- 而不是伪装成 `exact completion`

交互式 Gemini completion policy 建议收敛为：

- `CCB_REQ_ID` 仅用于把本次 ask 锚定到正确 user turn
- 先确认带 `CCB_REQ_ID` 的 user anchor 已落盘
- 之后只跟踪该 anchor 后新增的 `gemini` message
- 当出现属于该 anchor 的新 `gemini` reply，且 reply 内容稳定、session 文件经过短暂 settle window 后不再变化，视为 `completed`
- 若明确出现与该 anchor 对应的取消信息，则视为 `cancelled`
- 若 pane 死亡、session 丢失、JSON 长时间不可恢复，则视为 `failed`
- idle timeout 不再作为默认完成路径，只能作为显式 compatibility fallback

这里的“内容稳定”必须是结构化观察，而不是“最后一句文本看起来像结束了”。

建议最小状态机如下：

1. 发送前记录当前 session file、message count、last gemini id/hash 基线
2. 发送带 `CCB_REQ_ID` 的 user prompt
3. 等待 anchor user message 落盘
4. 观察 anchor 后是否出现新的 `gemini` message
5. 若新 `gemini` message 仍在被原地改写，则持续等待
6. 当最新 reply 文本、message id、message count、session `lastUpdated` 在 settle window 内保持稳定时，标记 `reply_stable`
7. `reply_stable` 才允许对外发布 `completed`

必须明确：

- `thoughts` 存在不代表仍未完成
- 只看到一条 `gemini` message 也不代表一定已完成，仍需等待 settle window
- 不能因为 pane 暂时静默就提前 completed
- 不能继续把 `CCB_DONE` 缺失简单等价为“模型忘了收尾”

#### 9.6.3 Activity log 与会话文件的边界

Gemini CLI 还存在 devtools/activity log JSONL 能力，但当前公开实现主要记录：

- `console`
- `network`

它不是稳定的 turn lifecycle 协议，不应直接作为 askd 的主完成信号。

因此 v2 中必须明确：

- `session-*.json` 是会话内容快照，不是协议终态流
- activity log JSONL 是调试/诊断信号，不是主完成信号
- 若未来 Gemini 官方公开稳定的 structured event stream，应优先迁移到该路径

#### 9.6.4 Gemini completion 元数据

建议 askd 内部对 `Gemini` 暴露以下 completion 元数据：

- `completion_status = completed | cancelled | failed | incomplete`
- `completion_reason = stream_result | acp_end_turn | cancel_info | session_reply_stable | timeout | pane_dead | session_corrupt | legacy_quiet`
- `completion_confidence = exact | observed | degraded`
- `anchor_seen`
- `reply_started`
- `reply_stable`
- `session_path`
- `structured_mode`

其中：

- `exact` 仅用于 `stream-json result` 或 ACP `end_turn`
- `observed` 用于 pane-backed `session_reply_stable`
- `degraded` 用于 compatibility fallback

#### 9.6.5 实现约束

- `GeminiLogReader` 不应继续只返回“最新一段文本”，而应升级为暴露 `session_path`、`message_id`、`message_type`、`lastUpdated`、`stable_window` 等观察维度
- `Gemini` adapter 必须显式区分 structured mode 与 pane-backed mode
- 交互式模式下不得再把 `CCB_DONE` 作为唯一完成信号
- 交互式模式下不得默认依赖 idle timeout 判定成功
- `JSONDecodeError`、原地改写、mtime 粒度不足等 session file 特性必须纳入状态机
- 若未来 Gemini 官方稳定暴露 `result` / `end_turn` 类终态事件，应优先收敛到 exact path，而不是继续强化 session file 猜测逻辑

#### 9.6.6 Gemini adapter 状态机伪代码

建议把 Gemini adapter 显式拆成两个完成状态机，而不是在一个循环里混合判断。

structured mode 伪代码：

```text
submit(req):
  baseline = capture_structured_cursor()
  send(req)

  while before deadline:
    event = next_structured_event(baseline)

    if event is None:
      continue

    if event.kind == "assistant_chunk":
      reply_buffer.append(event.text)
      reply_started = true
      continue

    if event.kind == "tool_call":
      tool_active = true
      continue

    if event.kind == "tool_result":
      tool_active = false
      continue

    if event.kind == "result":
      return completed(
        reason = "stream_result",
        confidence = "exact",
        reply = select_final_reply(reply_buffer, event),
      )

    if event.kind == "acp_stop" and event.stop_reason == "end_turn":
      return completed(
        reason = "acp_end_turn",
        confidence = "exact",
        reply = select_final_reply(reply_buffer, event),
      )

    if event.kind == "acp_stop" and event.stop_reason in {"cancelled", "aborted"}:
      return cancelled(reason = "cancel_info", confidence = "exact")

    if event.kind == "error":
      return failed(reason = "transport_error", confidence = "exact")

  if compatibility_mode and reply_started:
    return completed(reason = "legacy_quiet", confidence = "degraded")

  return incomplete(reason = "timeout", confidence = "degraded")
```

pane-backed mode 伪代码：

```text
submit(req):
  baseline = capture_session_baseline()
  send(req_with_ccb_req_id)

  anchor_seen = false
  reply_started = false
  stable_since = null
  last_reply_fingerprint = null
  parse_failures = 0

  while before deadline:
    ensure_pane_alive()
    snapshot = read_session_snapshot_with_retry()

    if snapshot.parse_failed:
      parse_failures += 1
      if parse_failures > parse_failure_limit:
        return failed(reason = "session_corrupt", confidence = "observed")
      continue

    parse_failures = 0

    if !anchor_seen:
      anchor = find_user_anchor(snapshot, req_id)
      if anchor is None:
        continue
      anchor_seen = true
      anchor_cursor = anchor.cursor
      continue

    if detect_cancel_info(snapshot, anchor_cursor, req_id):
      return cancelled(reason = "cancel_info", confidence = "observed")

    reply = find_last_gemini_reply_after_anchor(snapshot, anchor_cursor)
    if reply is None:
      continue

    reply_started = true
    fingerprint = (
      reply.message_id,
      hash(reply.content),
      snapshot.message_count,
      snapshot.last_updated,
    )

    if fingerprint != last_reply_fingerprint:
      last_reply_fingerprint = fingerprint
      stable_since = now()
      continue

    if now() - stable_since >= settle_window:
      return completed(
        reason = "session_reply_stable",
        confidence = "observed",
        reply = reply.content,
      )

  if compatibility_mode and reply_started:
    return completed(reason = "legacy_quiet", confidence = "degraded")

  return incomplete(reason = "timeout", confidence = "degraded")
```

实现细则：

- `settle_window` 必须与 `poll_interval` 解耦，避免“刚读到 reply 就立刻完成”
- `fingerprint` 至少包含 `message_id + content_hash + message_count + lastUpdated`
- 若 session file 切换，必须重新确认 anchor 归属，而不是直接沿用旧 cursor
- `reply_started = true` 只能降低超时误判，不能单独宣布成功

这套方案的直接收益：

- 明确 Gemini 不能继续走“文本尾行 + 超时”这条脆弱路径
- structured mode 可获得与 Codex 类似的精确终态
- 交互式模式也能从“纯静默猜测”升级为“anchor + stable reply”的观测式完成
- 为后续切换到 Gemini 官方结构化协议保留清晰演进路径

## 10. askd 统一守护设计

### 10.1 单守护职责

每项目一个 `askd`，职责如下：

- 加载 project config
- 维护 agent registry
- 启动/附着 agent runtime
- 接收 ask 请求
- 调用 provider adapter
- 维护 job/event store
- 做健康检查与自动回收

### 10.2 守护协议

统一 job 协议：

- `submit`
- `get`
- `watch`
- `cancel`
- `ping`
- `attach`
- `restore`
- `shutdown`

### 10.2.1 Job Contract

askd 协议虽然是内部接口，但 v2 必须把 job contract 定义清楚，否则 `ask` / `pend` / `watch` / `cancel` 的用户语义无法闭环。

#### 提交语义

- `ccb ask ...` 默认是异步提交
- 单播提交创建 1 个 job
- 广播提交创建 1 个 submission 和 N 个 child jobs
- 广播下每个目标 agent 拥有独立 `job_id`，不能共享同一 job

`submit` 返回必须区分单播与广播两类回执：

- 单播：
  - `job_id`
  - `agent_name`
  - `status = accepted | queued | running`
  - `accepted_at`
- 广播：
  - `submission_id`
  - `jobs[]`
  - `accepted_at`

CLI 输出行为必须固定：

- `ccb ask agent1 from user "..."`
  - 输出 `job_id`
- `ccb ask all from system "..."`
  - 输出 `submission_id` 与每个 child `job_id`

#### 查询语义

- `get(job_id)`
  - 返回该 job 的权威状态
- `ccb pend <job_id>`
  - 精确读取该 job 的最新 reply / decision
- `ccb pend <agent_name>`
  - 读取该 agent 最近一个相关 job 的 reply / decision，属于便利接口
- `ccb watch <job_id>`
  - 精确订阅该 job 的 event / completion state
- `ccb watch <agent_name>`
  - 默认订阅该 agent 当前 active job；若无 active job，则回退最近 job

#### 取消语义

- `cancel(job_id)`
  - 只取消单个 job
- CLI 暴露：
  - `ccb cancel <job_id>`

边界必须明确：

- `cancel` 是 job 级操作
- `kill` 是项目级 teardown 操作
- 不允许把 `cancel` 和 `kill` 混为一谈

#### Job 状态

建议统一：

- `accepted`
- `queued`
- `running`
- `completed`
- `cancelled`
- `failed`
- `incomplete`

#### `task_id` / `reply_to` 的角色

- `task_id`
  - 业务语义 id，可由调用方注入，用于串联跨 agent 协作
- `reply_to`
  - 指向上游 `job_id` 或外部消息 id
- `job_id`
  - askd 内部权威执行 id

因此：

- `job_id` 不等同于 `task_id`
- `reply_to` 不等同于 `parent_job_id`
- 广播 fan-out 后多个 child jobs 可以共享同一个 `task_id`

### 10.2.2 API JSON 样例

为了让 handler、client、测试夹具保持一致，建议在文档中固定最小 API 样例。

`submit` 单播请求：

```json
{
  "api_version": 2,
  "op": "submit",
  "request": {
    "project_id": "proj_abc",
    "to_agent": "agent1",
    "from_actor": "user",
    "body": "请整理当前状态",
    "task_id": "task-1",
    "reply_to": null,
    "message_type": "ask",
    "delivery_scope": "single"
  }
}
```

`submit` 单播响应：

```json
{
  "api_version": 2,
  "ok": true,
  "job_id": "job_123",
  "agent_name": "agent1",
  "status": "accepted",
  "accepted_at": "2026-03-18T10:00:00Z"
}
```

`submit` 广播响应：

```json
{
  "api_version": 2,
  "ok": true,
  "submission_id": "sub_456",
  "accepted_at": "2026-03-18T10:00:00Z",
  "jobs": [
    {"job_id": "job_a", "agent_name": "agent1", "status": "accepted"},
    {"job_id": "job_b", "agent_name": "agent2", "status": "queued"}
  ]
}
```

`get(job_id)` 响应：

```json
{
  "api_version": 2,
  "ok": true,
  "job_id": "job_123",
  "status": "running",
  "agent_name": "agent1",
  "latest_reply_preview": "正在整理…",
  "completion": {
    "terminal": false,
    "confidence": "observed",
    "reason": null
  }
}
```

`cancel(job_id)` 响应：

```json
{
  "api_version": 2,
  "ok": true,
  "job_id": "job_123",
  "status": "cancelled",
  "cancel_requested_at": "2026-03-18T10:01:00Z"
}
```

`watch(job_id)` 事件样例：

```json
{
  "api_version": 2,
  "event_id": "evt_1",
  "job_id": "job_123",
  "agent_name": "agent1",
  "type": "completion_item",
  "timestamp": "2026-03-18T10:00:10Z",
  "payload": {
    "kind": "assistant_chunk",
    "text": "正在整理当前状态"
  }
}
```

约束：

- API payload 中不得直接暴露 provider 私有原始日志结构
- `watch` 必须输出标准化事件，而不是 provider 原始事件直通
- 单播和广播的回执结构必须保持稳定，便于 CLI 与脚本复用

### 10.2.3 协议版本与兼容失败

由于 v2 明确不以旧代码兼容为目标，CLI 与 askd 之间仍然必须保留显式协议版本边界，避免出现“同项目内二进制版本不一致但勉强继续跑”的隐蔽故障。

规则如下：

- 每个 askd request / response / watch event 都必须携带 `api_version`
- 当前文档定义的主版本固定为 `2`
- CLI 在首次连接 askd 时必须先校验 `api_version`
- 主版本不一致时，必须 hard fail，不允许 silent downgrade
- 次版本或附加字段扩展时，只允许 append-only，不允许重写已有字段语义

失败行为必须明确：

- CLI 版本高于 askd
  - 输出 `protocol_version_mismatch`
  - 提示重新拉起 askd
- askd 版本高于 CLI
  - 输出 `protocol_version_mismatch`
  - 提示升级 CLI
- `watch` 流中若发现跨代 askd 重连，必须通过新 `api_version` 与 `generation` 重新握手

这样做的目的：

- 让协议演进与 provider 演进解耦
- 避免调试时把版本错配误判为 provider 故障
- 让系统测试可以显式断言“不兼容时正确失败”

### 10.3 稳定性要求

守护必须具备：

- agent 级锁
- 原子写入
- crash-safe 状态落盘
- 启动恢复扫描
- pid / socket 陈旧检测
- event cursor 去重
- provider 超时隔离

### 10.3.1 失败分类与重试边界

为了避免不同模块各自发明错误语义，v2 需要把失败分类固定下来。

建议至少区分：

- `configuration_error`
  - 配置缺失、字段非法、保留关键字冲突
- `project_resolution_error`
  - 当前 cwd 无法解析到正确项目
- `workspace_error`
  - worktree/copy/inplace 初始化或校验失败
- `runtime_error`
  - pane/pty/headless 进程不存在、崩溃或无法附着
- `provider_error`
  - provider 启动失败、恢复失败、接口异常
- `completion_error`
  - source 解析失败、detector 无法推进、selector 异常
- `storage_error`
  - 原子写失败、状态文件损坏、cursor 落盘失败
- `ownership_error`
  - askd 归属冲突、安全接管失败

建议重试边界：

- `configuration_error`
  - 不自动重试
- `project_resolution_error`
  - 不自动重试
- `workspace_error`
  - 可进入 repair/fresh 路径，但不无限重试
- `runtime_error`
  - 可有限次重试 attach/start
- `provider_error`
  - 允许 provider 级有限重试
- `completion_error`
  - 只允许 source 读取级有限重试，不允许 detector 死循环重试
- `storage_error`
  - 允许短暂重试，但失败后必须 hard fail
- `ownership_error`
  - 不自动强抢，只返回明确信息

这样做的目的：

- 让 `doctor` 能输出稳定错误分类
- 让重试策略不再散落在各 provider adapter
- 避免“为了让任务继续跑下去”而无限吞错

### 10.3.2 askd 心跳、租约与接管规则

为了让“项目级持续挂载守护”真正稳定，v2 必须把 askd 的心跳与接管机制写成硬规则。

askd 必须维护一份 project-scoped `lease` 状态，至少包含：

- `project_id`
- `askd_pid`
- `socket_path`
- `owner_uid`
- `boot_id`
- `started_at`
- `last_heartbeat_at`
- `mount_state`

推荐固定落盘路径：

- `lease_path = .ccb/askd/lease.json`
- `socket_path = .ccb/askd/askd.sock`

心跳规则：

- askd 必须周期性刷新 `last_heartbeat_at`
- 心跳文件更新必须走原子写
- 只有在 socket 已成功绑定、registry 已加载完成后，askd 才允许把自己标记为 `mounted`

客户端判活规则：

- 同时满足以下条件，才视为 askd 仍然健康持有租约：
  - pid 仍存在
  - `last_heartbeat_at` 未超过 grace window
  - socket 可连接
- 只满足其中一部分时，状态必须降级为 `degraded`，不能直接当作健康

接管规则：

- pid 不存在时，可进入接管检查
- pid 存在但 heartbeat 已严重超时，且 socket 不可连接时，可进入接管检查
- 若旧 askd 仍可响应 socket，即使 heartbeat 落后，也不得强抢
- 接管前必须持有项目级启动锁，避免双 askd 并发拉起
- 接管成功后必须重写 lease，并递增内部 `generation`

实现约束：

- `generation` 变化后，旧 watch client 必须感知到 askd 已切换代际
- 任何 agent runtime attach 前都必须确认本地 askd 仍持有当前 lease
- `ccb kill` 或显式 unmount 时，必须先写 `mount_state=unmounted`，再关闭 socket 和子资源

### 10.3.3 状态落盘顺序

为了避免 `watch`、`pend`、`doctor` 看到互相矛盾的状态，v2 必须固定关键状态的落盘顺序。

最小顺序约束：

- `job accepted`
  - 先写 `JobRecord(status=accepted|queued)`
  - 再追加 `job_accepted` 或 `job_queued` 事件
- `job started`
  - 先写 `JobRecord(status=running)`
  - 再追加 `job_started`
- `completion terminal`
  - 先写 `CompletionDecision`
  - 再追加 `completion_terminal`
  - 最后把 `JobRecord.status` 推进到 `completed|cancelled|failed|incomplete`
- `runtime degraded`
  - 先写 `AgentRuntime.health`
  - 再追加 `runtime_degraded`

一致性要求：

- `pend` 读取 terminal 结果时，优先读 `CompletionDecision`
- `watch` 读取事件流时，不得早于其对应状态文件落盘时间对外宣告成功
- `doctor` 若检测到 `JobRecord.status=completed` 但缺少 terminal decision，必须报告 `storage_error`

### 10.4 askd 生命周期

v2 必须明确 askd 是“项目级持续挂载守护”，而不是短生命周期按需子进程。

生命周期规则：

- 第一次执行 `ccb [agents...]` 时，为当前项目启动 askd，并建立 `mounted` 状态
- askd 以 project-scoped 身份运行，并记录 `project_id`
- askd 启动后持续挂载，不因为暂时空闲、无在线 agent、无 watch client 而自动退出
- 已挂载项目内的 `ccb ask`、`ccb ping`、`ccb pend`、`ccb watch` 都复用该 askd
- askd 的卸载由显式命令触发，而不是 idle timeout 触发

建议默认：

- `idle_timeout = 0`
- 即默认关闭空闲自动退出

异常处理：

- askd 启动时必须清理陈旧 pid、socket、state file
- askd 需要持久化 `mount_state = mounted|unmounted`
- 若 `mount_state=mounted` 但 askd 进程已消失，下一次 `ccb ask` / `ccb ping` / `ccb pend` / `ccb watch` 请求应尝试自动拉起并恢复挂载
- 若 `mount_state=unmounted`，则 `ccb ask` / `ccb pend` / `ccb watch` 应直接失败，并提示先执行 `ccb [agents...]`
- `ccb ping` 在 `mount_state=unmounted` 时返回 `unmounted`，不隐式启动 askd
- 若发现 orphan askd，下一次请求应优先做 ownership 校验
- ownership 不匹配且旧 owner 已死亡时，允许安全接管
- ownership 不匹配但旧 owner 存活时，应拒绝强抢并返回明确信息

显式卸载路径：

- `ccb kill`：终止当前项目全部 agent，并卸载当前项目 askd
- `ccb kill -f`：清理全局孤儿资源与陈旧挂载状态

这比“空闲自动退出”更适合 `ccb ask`、`pend`、`watch`、后台广播等 agent-first 场景，也更符合“跟随 `ccb` 启动持续挂载”的使用心智。

### 10.5 观测与诊断命令映射

当前项目已有 `ccb-ping`、`pend`、`mounted` 等运维能力。v2 应在 agent-first 命令面中给出等价能力，而不是弱化可观测性。

建议映射：

- `ccb ping <agent|all>`：替代 provider-first `ccb-ping`
- `ccb pend <agent|job_id> [N]`：替代 provider-first `pend`
- `ccb cancel <job_id>`：暴露 askd job 级取消能力
- `ccb ps --alive`：替代 `mounted` 风格“当前在线项”检查
- `ccb watch <agent|job_id>`：流式观察 agent 或具体 job 的事件与回复
- `ccb doctor`：输出项目解析、askd 状态、workspace 绑定、provider health

补充约束：

- `ccb ping` 必须区分 `mounted`、`unmounted`、`degraded`、`running`
- `ccb ps --alive` 必须显示 askd 是否已挂载，而不只是 agent 是否在线
- `ccb pend` / `ccb watch` 在项目未挂载时不得隐式启动 askd

原则：

- agent-first 命令必须覆盖当前项目已有的最小诊断能力
- 新命令应基于 agent，而不是暴露 provider-first 内部结构

### 10.5.1 诊断输出 Schema

为了避免 `doctor` / `ps` / `ping` / `pend` / `watch` 在不同 provider 上各写各的输出，建议统一 schema。

`ccb ping <agent>` 最小输出字段：

- `project_id`
- `agent_name`
- `provider`
- `mount_state`
- `runtime_state`
- `health`
- `compatibility_mode`

`ccb ps --alive` 最小输出字段：

- `project_id`
- `askd_state`
- `agent_name`
- `provider`
- `runtime_mode`
- `workspace_mode`
- `state`
- `queue_depth`

`ccb doctor` 最小输出字段：

- `project`
- `project_id`
- `askd`
- `agents[]`

其中每个 `agents[]` 项至少包含：

- `agent_name`
- `provider`
- `runtime_mode`
- `workspace_path`
- `workspace_mode`
- `branch_name`
- `compatibility_mode`
- `completion_family`
- `completion_confidence`
- `last_completion_reason`
- `queue_depth`
- `health`

`ccb pend <job_id>` 最小输出字段：

- `job_id`
- `agent_name`
- `status`
- `reply`
- `completion_reason`
- `completion_confidence`

`ccb watch <job_id>` 最小事件字段：

- `event_id`
- `job_id`
- `agent_name`
- `type`
- `timestamp`
- `payload`

原则：

- 同一命令的 JSON 输出字段在 provider 间保持一致
- provider 特有附加字段可放入 `diagnostics`
- 人类可读渲染与 JSON 渲染共享同一数据模型，不得双维护

### 10.5.2 诊断命令 JSON 样例

为了让 CLI、脚本、测试夹具对同一输出结构形成稳定预期，v2 需要固定最小 JSON 样例。

`ccb ping agent1 --json`：

```json
{
  "project_id": "proj_abc",
  "agent_name": "agent1",
  "provider": "codex",
  "mount_state": "mounted",
  "runtime_state": "running",
  "health": "healthy",
  "compatibility_mode": "strict",
  "diagnostics": {
    "askd_generation": 3,
    "last_heartbeat_at": "2026-03-18T10:00:00Z"
  }
}
```

`ccb ps --alive --json`：

```json
{
  "project_id": "proj_abc",
  "askd_state": "mounted",
  "agents": [
    {
      "agent_name": "agent1",
      "provider": "codex",
      "runtime_mode": "pane-backed",
      "workspace_mode": "git-worktree",
      "state": "running",
      "queue_depth": 1
    },
    {
      "agent_name": "agent2",
      "provider": "claude",
      "runtime_mode": "headless",
      "workspace_mode": "git-worktree",
      "state": "idle",
      "queue_depth": 0
    }
  ]
}
```

`ccb pend job_123 --json`：

```json
{
  "job_id": "job_123",
  "agent_name": "agent1",
  "status": "completed",
  "reply": "当前状态已整理完成",
  "completion_reason": "task_complete",
  "completion_confidence": "exact",
  "updated_at": "2026-03-18T10:00:12Z"
}
```

`ccb doctor --json`：

```json
{
  "project": "/workspace/demo",
  "project_id": "proj_abc",
  "askd": {
    "state": "mounted",
    "pid": 23811,
    "socket_path": ".ccb/askd/askd.sock",
    "generation": 3,
    "health": "healthy"
  },
  "agents": [
    {
      "agent_name": "agent1",
      "provider": "codex",
      "runtime_mode": "pane-backed",
      "workspace_path": ".ccb/workspaces/agent1",
      "workspace_mode": "git-worktree",
      "branch_name": "ccb/agent1",
      "compatibility_mode": "strict",
      "completion_family": "protocol_turn",
      "completion_confidence": "exact",
      "last_completion_reason": "task_complete",
      "queue_depth": 1,
      "health": "healthy"
    }
  ]
}
```

约束：

- `--json` 输出字段顺序应稳定，便于 golden test
- 缺失字段必须显式输出 `null`，而不是随意省略
- 人类可读模式只是同一数据模型的另一种渲染，不得拥有额外隐藏字段

## 11. 数据模型

### 11.0 持久化 Schema Version 规则

v2 虽然不追求旧架构兼容，但所有落盘状态仍必须是“自描述”的，否则恢复、诊断、接管都会变得脆弱。

规则：

- 所有持久化 JSON 记录都必须带 `schema_version = 2`
- 所有顶层记录都必须带 `record_type`
- `record_type` 至少覆盖：
  - `agent_spec`
  - `agent_runtime`
  - `agent_restore_state`
  - `job_record`
  - `submission_record`
  - `job_event`
  - `completion_snapshot`
- JSONL 中的每一行记录也必须自带 `schema_version` 与 `record_type`

读取策略：

- `schema_version` 主版本不匹配时，必须 hard fail
- 允许读取包含额外未知字段的较新记录，但不得忽略已知字段类型错误
- `record_type` 不匹配时，不得尝试“猜测解析”

这样做的目的：

- 避免恢复逻辑依赖文件路径或字段偶然存在来猜类型
- 让 `doctor` 能准确报告“版本错配”而不是泛化成 storage_error
- 为未来的显式迁移工具保留边界

### 11.1 AgentSpec

静态配置模型：

- `name`
- `provider`
- `target`
- `workspace_mode`
- `workspace_root`
- `runtime_mode`
- `restore_default`
- `permission_default`
- `queue_policy`
- `compatibility_mode`
- `startup_args`
- `env`

#### 11.1.1 字段约束

- `name`
  - 项目内全局唯一
  - 不能与保留关键字冲突
- `provider`
  - 只表示具体 provider 适配器类型，不再承担身份语义
- `target`
  - 表示 provider 真实启动目标，例如 `codex`、`claude`
  - 允许与 `provider` 相同，也允许未来扩展为别名或二进制路径
- `workspace_mode`
  - 必须是 `git-worktree | copy | inplace`
- `runtime_mode`
  - 必须是 provider manifest 支持的合法模式
- `restore_default`
  - 必须是 `fresh | provider | auto`
- `permission_default`
  - 必须是 `manual | auto`
- `queue_policy`
  - 必须是 `serial-per-agent | reject-when-busy`
- `compatibility_mode`
  - 必须是 `strict | allow-fallback | legacy-primary`
- `startup_args`
  - 只允许表达 provider 启动参数，不允许塞入业务消息
- `env`
  - 只允许 agent 级进程环境覆盖，不允许修改用户全局配置

#### 11.1.2 Python 类型草案

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpec:
    name: str
    provider: str
    target: str
    workspace_mode: str
    workspace_root: str | None
    runtime_mode: str
    restore_default: str
    permission_default: str
    queue_policy: str
    compatibility_mode: str
    startup_args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
```

### 11.2 AgentRuntime

运行时模型：

- `agent_name`
- `state`
- `pid`
- `started_at`
- `last_seen_at`
- `provider_runtime_ref`
- `provider_session_ref`
- `workspace_path`
- `project_id`
- `backend_type`
- `queue_depth`
- `socket_path`
- `health`

#### 11.2.1 状态枚举与不变量

`AgentRuntime.state` 至少覆盖：

- `starting`
- `idle`
- `busy`
- `stopping`
- `stopped`
- `degraded`
- `failed`

运行时不变量：

- 同一 `agent_name` 在同一 `project_id` 下最多存在一个 active runtime
- `state in (idle, busy, degraded)` 时，`workspace_path` 必须非空
- `state in (idle, busy)` 时，`provider_runtime_ref` 必须有效
- `queue_depth > 0` 且 `state = idle` 只允许出现在派发前短窗口，不得长期悬挂

#### 11.2.2 Python 类型草案

```python
from dataclasses import dataclass


@dataclass
class AgentRuntime:
    agent_name: str
    state: str
    pid: int | None
    started_at: str | None
    last_seen_at: str | None
    provider_runtime_ref: str | None
    provider_session_ref: str | None
    workspace_path: str | None
    project_id: str
    backend_type: str
    queue_depth: int
    socket_path: str | None
    health: str
```

### 11.3 AgentRestoreState

恢复模型：

- `restore_mode`
- `last_checkpoint`
- `conversation_summary`
- `open_tasks`
- `files_touched`
- `base_commit`
- `head_commit`
- `last_restore_status`

#### 11.3.1 字段语义

- `restore_mode`
  - 记录本次实际采用的恢复模式，而不是配置默认值
- `last_checkpoint`
  - 指向最近一次成功 handoff / snapshot 产物
- `conversation_summary`
  - 必须是供后续 agent 恢复理解上下文的摘要文本
- `open_tasks`
  - 记录恢复后仍应继续推进的任务项
- `files_touched`
  - 记录本 agent 最近一轮执行中修改或明确审阅过的文件
- `base_commit` / `head_commit`
  - 仅在 git workspace 中要求存在
- `last_restore_status`
  - 必须是 `fresh | provider | checkpoint | failed`

#### 11.3.2 Python 类型草案

```python
from dataclasses import dataclass, field


@dataclass
class AgentRestoreState:
    restore_mode: str
    last_checkpoint: str | None
    conversation_summary: str
    open_tasks: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    base_commit: str | None = None
    head_commit: str | None = None
    last_restore_status: str | None = None
```

### 11.4 Job 与 Event

作业模型：

- `job_id`
- `submission_id`
- `agent_name`
- `provider`
- `request`
- `status`
- `terminal_decision`
- `cancel_requested_at`
- `created_at`
- `updated_at`

其中 `request` 推荐统一为消息信封：

- `project_id`
- `to_agent`
- `from_actor`
- `body`
- `task_id`
- `reply_to`
- `message_type`
- `delivery_scope`

事件模型：

- `event_id`
- `job_id`
- `agent_name`
- `type`
- `payload`
- `timestamp`

#### 11.4.1 MessageEnvelope

`request` 不应继续保持松散 dict，v2 必须把消息信封独立建模。

必须字段：

- `project_id`
- `to_agent`
- `from_actor`
- `body`
- `task_id`
- `reply_to`
- `message_type`
- `delivery_scope`

约束：

- `from_actor` 允许 `user | system | <agent_name>`
- `to_agent` 允许 `<agent_name> | all`
- `body` 不能为空
- `delivery_scope` 必须与 `to_agent` 一致
  - `to_agent=all` 时必须是 `broadcast`
  - `to_agent=<agent>` 时必须是 `single`

#### 11.4.2 JobRecord 字段约束

`JobRecord` 至少需要补齐以下语义字段：

- `status`
  - 必须是 `accepted | queued | running | completed | cancelled | failed | incomplete`
- `terminal_decision`
  - terminal 前允许为空
  - terminal 后必须存在
- `cancel_requested_at`
  - 仅在收到取消请求后写入
- `created_at` / `updated_at`
  - 必须单调递增，不允许回拨

执行约束：

- `job_id` 是 askd 内部唯一执行标识
- `submission_id` 只用于广播聚合，单播可为空
- `provider` 只用于诊断，不参与业务路由

#### 11.4.3 SubmissionRecord

由于广播提交会产生 `submission_id`，文档也应显式定义 submission 级模型，而不是只把它当作 job 上的一个可选字段。

`SubmissionRecord` 至少必须包含：

- `submission_id`
- `project_id`
- `from_actor`
- `target_scope`
- `task_id`
- `job_ids`
- `created_at`
- `updated_at`

建议用途：

- 广播 ask 的统一收据
- 后续汇总 fan-out 结果
- 为未来 `ccb submit-status <submission_id>` 这类命令预留数据模型

约束：

- `SubmissionRecord` 不是执行实体，不替代 `JobRecord`
- child job 的终态仍以各自 `job_id` 为准
- `submission_id` 仅负责聚合，不负责 completion 判定

#### 11.4.4 Job Event 类型

事件类型必须标准化，否则 `watch` 会退回 provider 私有格式。

至少必须定义：

- `job_accepted`
- `job_queued`
- `job_started`
- `job_cancel_requested`
- `job_cancelled`
- `job_failed`
- `job_completed`
- `completion_item`
- `completion_state_updated`
- `completion_terminal`
- `runtime_attached`
- `runtime_detached`
- `runtime_degraded`

payload 约束：

- `job_*` 事件
  - 只包含 job 生命周期字段
- `completion_item`
  - payload 必须可映射为 `CompletionItem`
- `completion_state_updated`
  - payload 必须可映射为 `CompletionState`
- `completion_terminal`
  - payload 必须可映射为 `CompletionDecision`
- `runtime_*`
  - 只描述 runtime 侧状态，不混入 reply 文本

这样可以让：

- `watch`
  - 直接稳定消费标准事件
- `pend`
  - 读取 terminal event 或 latest decision
- `doctor`
  - 聚合 runtime 与 completion 两类视图

#### 11.4.5 Python 类型草案

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MessageEnvelope:
    project_id: str
    to_agent: str
    from_actor: str
    body: str
    task_id: str | None
    reply_to: str | None
    message_type: str
    delivery_scope: str


@dataclass
class JobRecord:
    job_id: str
    submission_id: str | None
    agent_name: str
    provider: str
    request: MessageEnvelope
    status: str
    terminal_decision: dict[str, Any] | None
    cancel_requested_at: str | None
    created_at: str
    updated_at: str


@dataclass
class SubmissionRecord:
    submission_id: str
    project_id: str
    from_actor: str
    target_scope: str
    task_id: str | None
    job_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class JobEvent:
    event_id: str
    job_id: str
    agent_name: str
    type: str
    payload: dict[str, Any]
    timestamp: str
```

### 11.5 Completion 子系统数据模型

completion 子系统建议单独维护自己的模型层，不与 askd job model 混写。

原因：

- job 生命周期与 completion 生命周期并不完全等价
- 一个 job 会经历 `queued -> running -> terminal`
- completion 关注的是“running 期间何时判定本轮 turn 结束”
- `watch` / `pend` / `doctor` 也需要读取 completion 侧的中间状态

建议至少定义以下模型。

#### 11.5.1 CompletionProfile

描述当前 runtime 应该使用哪一种完成检测能力：

- `provider`
- `runtime_mode`
- `completion_family`
- `completion_source_kind`
- `supports_exact_completion`
- `supports_observed_completion`
- `supports_anchor_binding`
- `supports_reply_stability`
- `supports_terminal_reason`
- `supports_legacy_quiet_fallback`
- `selector_family`

用途：

- provider manifest 落地后的运行时实例化结果
- askd 用它来装配 `source + detector + selector`

#### 11.5.2 CompletionCursor

统一描述 source 的读取位置：

- `source_kind`
- `opaque_cursor`
- `session_path`
- `offset`
- `line_no`
- `event_seq`
- `updated_at`

原则：

- askd 不解析 `opaque_cursor` 内部语义
- cursor 由具体 source 生成和推进
- detector 只能持有 cursor 引用，不能反向推导 provider 私有结构

#### 11.5.3 CompletionItem

source 输出给 detector 的最小标准事件：

- `kind`
- `timestamp`
- `cursor`
- `provider`
- `agent_name`
- `req_id`
- `payload`

`CompletionItem.kind` 至少必须覆盖：

- `anchor_seen`
- `assistant_chunk`
- `assistant_final`
- `tool_call`
- `tool_result`
- `result`
- `turn_boundary`
- `turn_aborted`
- `cancel_info`
- `error`
- `pane_dead`
- `session_snapshot`
- `session_mutation`
- `session_rotate`

约束：

- source 必须先做 provider 私有字段清洗，再生成 `CompletionItem`
- detector 不直接消费 provider 原始 JSON / 文本

#### 11.5.4 CompletionState

detector 运行中的内部状态快照：

- `anchor_seen`
- `reply_started`
- `reply_stable`
- `tool_active`
- `subagent_activity_seen`
- `last_reply_hash`
- `last_reply_at`
- `stable_since`
- `provider_turn_ref`
- `latest_cursor`
- `terminal`

用途：

- 供 detector 自己推进状态机
- 供 `watch` / `doctor` 输出中间诊断视图
- 供 crash 恢复时保留必要上下文

#### 11.5.5 CompletionDecision

detector 对外输出的统一终态结果：

- `terminal`
- `status`
- `reason`
- `confidence`
- `reply`
- `anchor_seen`
- `reply_started`
- `reply_stable`
- `provider_turn_ref`
- `source_cursor`
- `finished_at`
- `diagnostics`

其中：

- `status = completed | cancelled | failed | incomplete`
- `confidence = exact | observed | degraded`
- `diagnostics` 用于保留额外上下文，例如 `pane_dead=true`、`parse_failures=2`

#### 11.5.6 ReplyCandidate

reply selector 不应直接扫描原始日志，而应消费标准候选项：

- `kind`
- `text`
- `timestamp`
- `provider_turn_ref`
- `priority`
- `cursor`

`ReplyCandidate.kind` 必须限制在以下枚举中：

- `last_agent_message`
- `final_answer`
- `assistant_final`
- `assistant_chunk_merged`
- `session_reply`
- `fallback_text`

#### 11.5.6.1 Reply 选择优先级规则

reply selector 必须有统一优先级，否则不同 provider 容易各自返回不同“最终答案”。

统一优先级必须固定为：

1. terminal event 自带的显式最终消息
2. `last_agent_message`
3. `final_answer`
4. `assistant_final`
5. 合并后的 `assistant_chunk_merged`
6. `session_reply`
7. `fallback_text`

附加规则：

- 只有在 `CompletionDecision.terminal = true` 后才允许 select
- selector 不得因为“当前文本看起来像完整句子”就提前选中
- 若上层存在更高优先级候选，低优先级候选必须被覆盖
- selector 结果必须可复现，同一输入候选集必须返回相同结果

这样可以避免：

- Codex 选到中间 assistant 文本
- Claude interactive 选到 progress 文本
- Gemini pane-backed 选到还未稳定的旧 snapshot reply

#### 11.5.7 CompletionSnapshot

为了让 `pend` / `watch` / `doctor` 统一读到当前状态，askd 必须持久化轻量 completion snapshot：

- `job_id`
- `agent_name`
- `profile_family`
- `state`
- `latest_decision`
- `latest_reply_preview`
- `updated_at`

原则：

- snapshot 是运行时观测面，不是历史归档
- terminal 后 snapshot 可转入 job/event store
- 非 terminal 状态下 snapshot 应支持覆盖更新

#### 11.5.8 Completion 类型草案

实现时必须先固定 completion 领域枚举。

必须定义：

- `CompletionStatus`
  - `accepted`
  - `queued`
  - `running`
  - `completed`
  - `cancelled`
  - `failed`
  - `incomplete`
- `CompletionConfidence`
  - `exact`
  - `observed`
  - `degraded`
- `CompletionFamily`
  - `protocol_turn`
  - `structured_result`
  - `session_boundary`
  - `anchored_session_stability`
  - `legacy_text_quiet`
- `CompletionSourceKind`
  - `protocol_event_stream`
  - `structured_result_stream`
  - `session_event_log`
  - `session_snapshot`
  - `terminal_text`
- `CompatibilityMode`
  - `strict`
  - `allow-fallback`
  - `legacy-primary`

`CompletionReason` 必须统一为字符串枚举，而不是随意拼写文本。至少覆盖：

- `task_complete`
- `turn_aborted`
- `result_message`
- `stream_result`
- `acp_end_turn`
- `turn_duration`
- `session_reply_stable`
- `cancel_info`
- `api_error`
- `transport_error`
- `pane_dead`
- `session_corrupt`
- `timeout`
- `legacy_done_marker`
- `legacy_quiet`

这样做的直接收益：

- `doctor` / `pend` / `watch` 的展示字段可稳定枚举
- 回归测试可以精确断言 reason/confidence
- 避免未来继续出现 `turn_complete` / `task_complete` / `completed` 混着写的情况

#### 11.5.9 Python 类型草案

为了降低实现阶段的二次设计成本，建议直接按 Python dataclass / protocol 方式落地。

示意：

```python
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class CompletionStatus(str, Enum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


@dataclass
class CompletionCursor:
    source_kind: str
    opaque_cursor: str
    session_path: str | None = None
    offset: int | None = None
    line_no: int | None = None
    event_seq: int | None = None
    updated_at: str | None = None


@dataclass
class CompletionItem:
    kind: str
    timestamp: str
    cursor: CompletionCursor
    provider: str
    agent_name: str
    req_id: str
    payload: dict[str, Any]


@dataclass
class CompletionDecision:
    terminal: bool
    status: CompletionStatus
    reason: str | None
    confidence: str | None
    reply: str
    anchor_seen: bool
    reply_started: bool
    reply_stable: bool
    provider_turn_ref: str | None
    source_cursor: CompletionCursor | None
    finished_at: str | None
    diagnostics: dict[str, Any]


class CompletionSource(Protocol):
    def capture_baseline(self) -> CompletionCursor: ...
    def poll(self, cursor: CompletionCursor, timeout_s: float) -> CompletionItem | None: ...


class CompletionDetector(Protocol):
    def bind(self, request_ctx: Any, baseline: CompletionCursor) -> None: ...
    def ingest(self, item: CompletionItem) -> None: ...
    def decision(self) -> CompletionDecision: ...


class ReplySelector(Protocol):
    def ingest_candidate(self, candidate: Any) -> None: ...
    def select(self, decision: CompletionDecision) -> str: ...
```

约束：

- 实现时应优先使用显式 dataclass / protocol
- 不建议把这层先做成松散 dict 传递
- provider 私有补充字段统一放进 `payload` / `diagnostics`

补充说明：

- `accepted | queued | running` 属于 `JobRecord.status`，不属于 `CompletionStatus`
- `CompletionStatus` 只表达 terminal decision 的最终完成语义
- `CompletionDecision.terminal = false` 时，`status` 应固定为 `incomplete`

### 11.6 Completion 模块布局

建议 completion 子系统独立成一组模块，而不是散落在各 provider adapter 下。

#### 11.6.0 代码组织原则

v2 必须把“文件结构清晰、文件功能纯粹、避免巨石文件”写成硬约束，而不是实现阶段的个人风格选择。

核心原则：

- 一个目录只表达一层架构语义
  - 例如 `completion/` 只负责完成检测
  - `providers/` 只负责 provider 适配
  - `workspace/` 只负责工作区规划与落盘
- 一个文件只承担一种主职责
  - `models.py` 只放数据模型
  - `registry.py` 只放装配逻辑
  - `orchestration.py` 只放流程编排
- 一个模块最多承担一条主控制流
  - 例如 `submit` 编排不能和 session 解析、日志扫描、selector 规则混在同一个文件
- provider 私有逻辑不得泄漏到 core 模块
- 诊断输出逻辑不得反向污染状态机逻辑

禁止的反模式：

- `askd.py` 之类的巨石入口文件同时承担 CLI 解析、socket 协议、job 管理、provider 调用、completion 判定
- `providers/codex.py` 这类单文件同时承担 pane 管理、日志解析、完成检测、reply 选择、错误恢复
- `models.py` 同时包含数据结构、文件 IO、业务逻辑
- 为了“方便”把 5 到 8 个相邻模块重新揉回一个大文件

建议拆分阈值：

- 单文件超过约 300 到 400 行，必须审查是否出现职责混杂
- 单文件出现 3 类以上领域概念时，必须拆分
  - 例如同时出现 `job + provider + completion`
- 单文件出现多个状态机时，必须拆分
- 单文件既读写磁盘、又做协议解析、又做状态推进时，必须拆分

允许少量例外：

- `models.py` 这类纯数据声明文件可以略长
- 很薄的 facade 文件可以只做转发与装配

但即使是例外，也必须满足：

- 逻辑密度低
- 无多条主控制流
- 无跨领域副作用

#### 11.6.0.1 推荐目录边界

建议顶层按“稳定职责”分目录，而不是按历史脚本来源分目录：

```text
lib/
  cli/
  askd/
  agents/
  providers/
  completion/
  workspace/
  project/
  history/
  terminal/
  storage/
```

建议目录职责：

- `cli/`
  - 参数解析
  - 命令分发
  - 用户输出格式化
- `askd/`
  - daemon 生命周期
  - socket/API 协议
  - job 编排
- `agents/`
  - `AgentSpec`
  - `AgentRuntime`
  - agent 状态机
- `providers/`
  - provider manifest
  - adapter
  - provider-specific source builder
- `completion/`
  - source / detector / selector / registry
- `workspace/`
  - worktree/copy/inplace 规划
  - workspace 初始化、校验、清理
- `project/`
  - 项目解析
  - `.ccb` 发现
  - project_id 规则
- `history/`
  - snapshot/handoff 产物生成
- `terminal/`
  - tmux / WezTerm / PTY backend
- `storage/`
  - state file、jsonl、atomic write、cursor persistence

#### 11.6.0.2 依赖方向约束

目录依赖建议单向流动：

- `cli -> askd -> agents/providers/completion/workspace/project/storage`
- `providers -> completion.models`
- `completion -> storage.models`
- `workspace -> project/storage`

禁止：

- `completion` 反向依赖 `providers` 具体实现
- `storage` 依赖 `providers`
- `cli` 直接扫描 provider session 文件
- `providers` 直接写 `doctor`/`pend` 最终输出格式

如果某处出现循环依赖，优先处理方式不是“局部 import”，而是继续拆模块。

#### 11.6.0.3 推荐完整文件树

建议 v2 直接按下面的完整骨架落盘，而不是边做边长目录：

```text
lib/
  cli/
    main.py
    parser.py
    context.py
    commands/
      start.py
      ask.py
      cancel.py
      kill.py
      ps.py
      ping.py
      pend.py
      watch.py
      logs.py
      doctor.py
      config.py
    renderers/
      plain.py
      table.py
      json.py
  askd/
    main.py
    app.py
    api_models.py
    socket_server.py
    socket_client.py
    handlers/
      submit.py
      get.py
      watch.py
      cancel.py
      ping.py
      attach.py
      restore.py
      shutdown.py
    services/
      registry.py
      dispatcher.py
      mount.py
      ownership.py
      health.py
      snapshot_writer.py
  agents/
    models.py
    config_loader.py
    runtime_store.py
    state_machine.py
    policies.py
  providers/
    models.py
    catalog.py
    manifest_loader.py
    base/
      adapter.py
      runtime.py
      source_builder.py
      errors.py
    codex/
      manifest.py
      adapter.py
      source.py
      candidates.py
    claude/
      manifest.py
      adapter.py
      main_session_source.py
      subagent_source.py
      candidates.py
    gemini/
      manifest.py
      adapter.py
      structured_source.py
      snapshot_source.py
      candidates.py
    legacy/
      adapter.py
      text_source.py
      candidates.py
  completion/
    models.py
    profiles.py
    registry.py
    orchestration.py
    sources/
      base.py
      protocol_event.py
      structured_result.py
      session_log.py
      session_snapshot.py
      legacy_text.py
    detectors/
      base.py
      protocol_turn.py
      structured_result.py
      session_boundary.py
      anchored_session_stability.py
      legacy_text_quiet.py
    selectors/
      base.py
      final_message.py
      structured_result.py
      session_reply.py
  workspace/
    models.py
    planner.py
    git_worktree.py
    copy_mode.py
    inplace_mode.py
    validator.py
    cleanup.py
  project/
    resolver.py
    discovery.py
    ids.py
  history/
    snapshot.py
    handoff.py
    templates.py
  terminal/
    models.py
    registry.py
    tmux_backend.py
    wezterm_backend.py
    pty_backend.py
  storage/
    paths.py
    atomic.py
    locks.py
    json_store.py
    jsonl_store.py
    cursor_store.py
```

目的：

- 新人第一次看目录就能知道东西该放哪
- 任何模块膨胀时，都有明确的拆分落点
- 不必把后续新增逻辑继续塞回已有大文件

#### 11.6.1 `askd/` 文件级设计

`askd/` 必须是“daemon 编排层”，而不是第二个巨石业务层。

建议文件职责：

- `main.py`
  - 进程入口
  - 仅负责启动 app
- `app.py`
  - 组装 socket server、service registry、shutdown hook
- `api_models.py`
  - askd API request/response 模型
- `socket_server.py`
  - 本地 socket 服务端
- `socket_client.py`
  - CLI 侧调用 askd 的客户端
- `handlers/submit.py`
  - 只处理 submit 请求到 service 调用
- `handlers/get.py`
  - 只处理 get 请求
- `handlers/watch.py`
  - 只处理 watch 订阅
- `handlers/cancel.py`
  - 只处理 cancel 请求
- `handlers/ping.py`
  - 只处理健康检查
- `handlers/attach.py`
  - 只处理 agent attach
- `handlers/restore.py`
  - 只处理 restore 命令入口
- `handlers/shutdown.py`
  - 只处理项目级 kill / askd 卸载入口
- `services/registry.py`
  - agent runtime 注册表
- `services/dispatcher.py`
  - job 入队、出队、调度
- `services/mount.py`
  - mount_state 管理
- `services/ownership.py`
  - askd 归属校验与安全接管
- `services/health.py`
  - 周期性健康检查与回收
- `services/snapshot_writer.py`
  - completion snapshot / job snapshot 持久化

硬约束：

- `handlers/*` 不得直接访问 provider 私有实现
- `services/dispatcher.py` 不得直接解析 provider 输出
- `app.py` 不得写业务规则，只做装配

#### 11.6.2 `providers/` 文件级设计

`providers/` 必须只负责 provider 差异适配，不负责系统级决策。

建议通用层：

- `models.py`
  - provider manifest / runtime ref / session ref 基础模型
- `catalog.py`
  - provider 注册表
- `manifest_loader.py`
  - manifest 加载与校验
- `base/adapter.py`
  - `ProviderAdapter` 抽象接口
- `base/runtime.py`
  - provider runtime 抽象
- `base/source_builder.py`
  - 把 provider runtime 映射到 completion source builder
- `base/errors.py`
  - provider 侧标准异常

建议 provider 专用层：

- `codex/adapter.py`
  - 只做 Codex runtime 启停、提交、恢复、取消
- `codex/source.py`
  - 只把 Codex 输出接到标准 source
- `codex/candidates.py`
  - 只产出 reply candidates

- `claude/adapter.py`
  - 只做 Claude runtime 管理
- `claude/main_session_source.py`
  - 主会话 source
- `claude/subagent_source.py`
  - 子活动 source
- `claude/candidates.py`
  - reply candidates

- `gemini/adapter.py`
  - 只做 Gemini runtime 管理
- `gemini/structured_source.py`
  - structured path source
- `gemini/snapshot_source.py`
  - pane-backed snapshot source
- `gemini/candidates.py`
  - reply candidates

- `legacy/adapter.py`
  - legacy provider 的通用适配封装
- `legacy/text_source.py`
  - `CCB_DONE + quiet` 兼容 source
- `legacy/candidates.py`
  - legacy reply candidates

硬约束：

- provider 专用目录不得直接定义 detector
- provider 专用目录不得直接持久化 askd job store
- provider 专用目录不得实现 `doctor` 最终渲染

#### 11.6.3 `completion/` 文件级设计

`completion/` 是整个架构的核心纯逻辑层，必须保持最干净。

建议文件职责：

- `models.py`
  - 所有 completion 领域模型
- `profiles.py`
  - `CompletionProfile` 与 profile 解析
- `registry.py`
  - 按 profile 装配 source / detector / selector
- `orchestration.py`
  - 统一提交后轮询主循环
- `sources/base.py`
  - source 抽象基类
- `sources/protocol_event.py`
  - 协议事件 source
- `sources/structured_result.py`
  - headless/structured result source
- `sources/session_log.py`
  - 顺序日志 source
- `sources/session_snapshot.py`
  - snapshot polling source
- `sources/legacy_text.py`
  - legacy text source
- `detectors/base.py`
  - detector 抽象基类
- `detectors/protocol_turn.py`
  - `task_complete` 类终态检测
- `detectors/structured_result.py`
  - `result` 类终态检测
- `detectors/session_boundary.py`
  - `assistant -> turn_duration` 类边界检测
- `detectors/anchored_session_stability.py`
  - anchor + settle window 类检测
- `detectors/legacy_text_quiet.py`
  - legacy quiet detector
- `selectors/base.py`
  - selector 抽象接口
- `selectors/final_message.py`
  - final message / last agent message 优先级选择
- `selectors/structured_result.py`
  - structured result reply 选择
- `selectors/session_reply.py`
  - snapshot/log reply 选择

硬约束：

- `orchestration.py` 不得读取 provider 私有文件格式
- `detectors/*` 不得直接读写磁盘
- `selectors/*` 不得推进状态机
- `registry.py` 只做装配，不做运行时判断

#### 11.6.4 其他目录的文件纯度要求

为避免巨石文件回流，其他目录也应有同样约束：

- `workspace/`
  - `planner.py` 只算路径和模式
  - `git_worktree.py` 只做 worktree 操作
  - `validator.py` 只做校验
  - `cleanup.py` 只做回收
- `project/`
  - `resolver.py` 只负责项目归属解析
  - `discovery.py` 只负责 `.ccb` 发现
  - `ids.py` 只负责 `project_id` 规则
- `terminal/`
  - 每个 backend 一个文件
  - `registry.py` 只做 backend 选择
- `storage/`
  - `atomic.py` 只做原子写
  - `json_store.py` / `jsonl_store.py` 只做存取
  - `locks.py` 只做锁
  - `paths.py` 只做路径规则

这些目录都不应跨层偷做编排逻辑。

### 11.6.5 类与接口草案

在目录和文件边界明确后，v2 还需要提前固化核心类与接口草案，避免实现阶段重新长出新的耦合。

目标：

- 让每个文件都有明确入口对象
- 让模块之间通过稳定接口协作
- 让测试能够直接替换 fake 实现

#### 11.6.5.1 `cli/` 核心类

`cli/main.py`

- `CliApp`
  - `run(argv) -> int`
  - 职责：CLI 启动入口，只负责串起 parser 与 command runner

`cli/parser.py`

- `CliParser`
  - `parse(argv) -> ParsedCommand`
  - 职责：参数解析，不做 IO，不做业务

`cli/context.py`

- `CliContextBuilder`
  - `build(parsed) -> CliContext`
  - 职责：解析当前项目、用户 cwd、输出模式、socket 目标

`cli/commands/*.py`

每个命令文件建议只暴露一个 command object：

- `StartCommand`
- `AskCommand`
- `CancelCommand`
- `KillCommand`
- `PsCommand`
- `PingCommand`
- `PendCommand`
- `WatchCommand`
- `LogsCommand`
- `DoctorCommand`
- `ConfigCommand`

统一接口建议：

- `execute(ctx, parsed) -> int | CommandResult`

约束：

- command 不直接访问 provider 私有实现
- command 不直接读写 `.ccb/agents/...` 原始文件
- command 与 askd 通讯统一经 `socket_client.py`

#### 11.6.5.2 `askd/` 核心类

`askd/app.py`

- `AskdApp`
  - `start()`
  - `shutdown()`
  - 职责：daemon 生命周期组装

`askd/socket_server.py`

- `AskdSocketServer`
  - `serve_forever()`
  - `register_handler(op, handler)`
  - 职责：本地 socket 服务端

`askd/socket_client.py`

- `AskdClient`
  - `submit(req) -> SubmitResponse`
  - `get(job_id) -> GetResponse`
  - `watch(target) -> EventStream`
- `cancel(job_id) -> CancelResponse`
- `ping(target) -> PingResponse`
- `attach(agent) -> AttachResponse`
- `restore(agent) -> RestoreResponse`
- `shutdown() -> ShutdownResponse`
  - 职责：CLI 与 askd 通讯封装

`askd/services/registry.py`

- `AgentRegistry`
  - `get(agent_name)`
  - `upsert(runtime)`
  - `remove(agent_name)`
  - `list_alive()`
  - 职责：agent runtime 注册表

`askd/services/dispatcher.py`

- `JobDispatcher`
  - `submit(job_request) -> JobReceipt`
  - `cancel(job_id) -> CancelResult`
  - `tick()`
  - 职责：job 排队与派发

- `AgentQueue`
  - `push(job)`
  - `peek()`
  - `pop()`
  - 职责：单 agent 队列抽象

`askd/services/mount.py`

- `MountManager`
  - `load_state()`
  - `mark_mounted()`
  - `mark_unmounted()`
  - 职责：项目挂载状态管理

`askd/services/ownership.py`

- `OwnershipGuard`
  - `verify_or_takeover()`
  - 职责：askd 所有权与安全接管

`askd/services/health.py`

- `HealthMonitor`
  - `check_all()`
  - `collect_orphans()`
  - 职责：runtime 健康检查

`askd/services/snapshot_writer.py`

- `SnapshotWriter`
  - `write_completion(snapshot)`
  - `write_job(job_state)`
  - 职责：运行时 snapshot 落盘

#### 11.6.5.3 `providers/` 核心类

`providers/base/adapter.py`

- `ProviderAdapter`
  - `prepare(agent_spec, runtime_spec)`
  - `start(agent_spec, launch_spec) -> ProviderRuntimeRef`
  - `attach(runtime_ref)`
  - `health(runtime_ref) -> HealthStatus`
- `submit(job_request, runtime_ref) -> ProviderSubmission`
- `cancel(job_ref, runtime_ref)`
- `restore(agent_state, runtime_ref)`
- `shutdown(runtime_ref)`
  - 职责：provider 运行时统一抽象

`providers/base/source_builder.py`

- `ProviderSourceBuilder`
  - `build(runtime_ref, profile) -> CompletionSource`
  - `build_candidates(runtime_ref, profile) -> ReplyCandidateSource`
  - 职责：provider 到 completion 的桥接点

`providers/catalog.py`

- `ProviderCatalog`
  - `get(provider_name) -> ProviderAdapter`
  - `get_manifest(provider_name) -> ProviderManifest`
  - 职责：provider 注册中心

阶段 2 过渡建议：

- 若当前代码库尚未完成 `providers/` 目录迁移，可先以：
  - `lib/provider_models.py`
  - `lib/provider_catalog.py`
 形式落地同一套接口语义
- 等 provider adapter 迁移开始后，再整体并入 `providers/`

provider 专用目录建议每个只暴露一个主 adapter：

- `CodexAdapter`
- `ClaudeAdapter`
- `GeminiAdapter`
- `LegacyProviderAdapter`

并各自搭配：

- `CodexSourceBuilder`
- `ClaudeSourceBuilder`
- `GeminiSourceBuilder`
- `LegacySourceBuilder`

约束：

- adapter 只做 provider transport / session / runtime 管理
- source builder 才是 provider 输出接入 completion 的边界
- adapter 不得自己直接决定 `completed`

#### 11.6.5.4 `completion/` 核心类

`completion/orchestration.py`

- `CompletionOrchestrator`
  - `run(request_ctx, source, detector, selector) -> CompletionDecision`
  - 职责：驱动统一轮询/终态判定主循环

`completion/registry.py`

- `CompletionRegistry`
  - `build_profile(agent_spec, runtime_ref, provider_manifest) -> CompletionProfile`
  - `build_source(profile, runtime_ref) -> CompletionSource`
  - `build_detector(profile) -> CompletionDetector`
  - `build_selector(profile) -> ReplySelector`
  - 职责：按 profile 装配 completion 组件

阶段 2 第一波建议：

- 第一波至少实现：
  - `build_profile()`
  - `build_detector()`
  - `build_selector()`
- `build_source()` 可在接入真实 provider source 时补齐

`completion/sources/base.py`

- `CompletionSource`
  - `capture_baseline() -> CompletionCursor`
  - `poll(cursor, timeout_s) -> CompletionItem | None`
  - 职责：统一 source 接口

`completion/detectors/base.py`

- `CompletionDetector`
  - `bind(request_ctx, baseline)`
  - `ingest(item)`
  - `decision() -> CompletionDecision`
  - 职责：统一 detector 接口

`completion/selectors/base.py`

- `ReplySelector`
  - `ingest_candidate(candidate)`
  - `select(decision) -> str`
  - 职责：统一 reply 选择接口

具体 detector 建议类名：

- `ProtocolTurnDetector`
- `StructuredResultDetector`
- `SessionBoundaryDetector`
- `AnchoredSessionStabilityDetector`
- `LegacyTextQuietDetector`

具体 selector 建议类名：

- `FinalMessageSelector`
- `StructuredResultSelector`
- `SessionReplySelector`

#### 11.6.5.5 `workspace/` 核心类

`workspace/planner.py`

- `WorkspacePlanner`
  - `plan(agent_spec, project_ctx) -> WorkspacePlan`
  - 职责：只计算路径、模式、branch 方案

`workspace/git_worktree.py`

- `GitWorktreeManager`
  - `ensure(plan) -> WorkspaceRef`
  - `cleanup(workspace_ref)`
  - 职责：只做 git worktree 生命周期

`workspace/copy_mode.py`

- `CopyWorkspaceManager`
  - `ensure(plan) -> WorkspaceRef`
  - `refresh(workspace_ref)`
  - 职责：copy 模式生命周期

`workspace/inplace_mode.py`

- `InplaceWorkspaceManager`
  - `ensure(plan) -> WorkspaceRef`
  - 职责：inplace 模式校验与引用

`workspace/validator.py`

- `WorkspaceValidator`
  - `validate(workspace_ref) -> ValidationResult`
  - 职责：工作区一致性校验

#### 11.6.5.6 `storage/` 核心类

`storage/paths.py`

- `PathLayout`
  - `project_root(...)`
  - `agent_dir(...)`
  - `job_store(...)`
  - `snapshot_path(...)`
  - 职责：统一路径规则

`storage/atomic.py`

- `AtomicWriter`
  - `write_text(path, text)`
  - `write_json(path, obj)`
  - 职责：原子写

`storage/json_store.py`

- `JsonStore`
  - `load(path, model)`
  - `save(path, model)`
  - 职责：结构化 JSON 文件存取

`storage/jsonl_store.py`

- `JsonlStore`
  - `append(path, row)`
  - `read_since(path, cursor)`
  - 职责：顺序事件流存取

`storage/cursor_store.py`

- `CursorStore`
  - `load(job_id)`
  - `save(job_id, cursor)`
  - 职责：watch/source cursor 持久化

#### 11.6.5.7 类设计总约束

为了避免类设计再次滑向巨石对象，建议统一遵守：

- 一个类最多只拥有一种外部资源
  - 例如只管理 socket，或只管理 session file，或只管理 queue
- 一个类最多只暴露一组相邻操作
  - 例如 `load/save`，或 `bind/ingest/decision`
- facade 类允许依赖多个组件，但 facade 内不写细节算法
- stateful 类必须把状态限定在本领域，不跨层缓存别的子系统信息

如果某个类开始同时感知：

- provider runtime
- completion detector
- job store
- CLI render

说明拆分已经失败，必须回退重构。

建议文件布局：

```text
lib/
  completion/
    models.py
    profiles.py
    registry.py
    orchestration.py
    sources/
      base.py
      protocol_event.py
      structured_result.py
      session_log.py
      session_snapshot.py
      legacy_text.py
    detectors/
      base.py
      protocol_turn.py
      structured_result.py
      session_boundary.py
      anchored_session_stability.py
      legacy_text_quiet.py
    selectors/
      base.py
      final_message.py
      structured_result.py
      session_reply.py
```

模块职责建议：

- `models.py`
  - `CompletionItem`
  - `CompletionDecision`
  - `CompletionState`
  - `CompletionCursor`
- `profiles.py`
  - `CompletionProfile`
  - manifest 到 profile 的解析
- `registry.py`
  - 按 profile 装配 detector / source / selector
- `orchestration.py`
  - 驱动统一轮询循环
- `sources/*`
  - provider 输出规范化
- `detectors/*`
  - 终态判断状态机
- `selectors/*`
  - 终态后选择最终回复

实现约束：

- provider adapter 只允许依赖 `registry.py` 与 `orchestration.py`
- provider adapter 不应直接 import 某个具体 detector
- detector 之间不得互相依赖
- selector 不得反向修改 detector state

### 11.7 askd 与 completion 的集成边界

askd 与 completion 子系统的边界也应明确。

askd 负责：

- job 创建
- runtime 获取
- source/detector/selector 装配
- timeout / cancellation / ownership 管理
- completion snapshot 持久化
- terminal decision 写回 job/event store

completion 子系统负责：

- 统一消费 source item
- 输出 `CompletionDecision`
- 输出 reply candidate 选择结果
- 输出中间 state 供 `watch` / `doctor` 使用

`watch` / `pend` / `doctor` 建议读取路径：

- `watch`
  - 优先读 `CompletionSnapshot.state`
  - 再流式追加 `CompletionItem`
- `pend`
  - 读 `CompletionDecision.reply`
  - 若未 terminal，则退回 `latest_reply_preview`
- `doctor`
  - 读 `CompletionProfile`
  - 读 `CompletionState`
  - 显示 `confidence` 与 `reason`

这样可以避免：

- `pend` 直接扫 provider 私有日志
- `watch` 直接绑定 provider 原始事件格式
- `doctor` 因 provider 差异而输出风格不一致

## 12. 并发策略

### 12.1 支持的并发形式

系统支持：

- 同项目多个不同 agent 并发
- 同项目多个同 provider agent 并发
- 不同项目各自独立 askd 并发

### 12.2 不支持的并发形式

系统不支持：

- 同名 agent 多 runtime 并发
- 一个 provider session 同时绑定多个 agent
- 多个 agent 共享同一个写工作区且默认认为安全

### 12.3 合并策略不内置自动化

如果 agent 基于 git worktree 工作：

- 每个 agent 在独立分支 / worktree 中完成工作
- CCB 记录它的 `base_commit`、`head_commit`
- 是否合并、何时合并、谁来合并，由用户明确决策

CCB 不默认替用户自动合并。

## 13. 测试策略

### 13.1 测试目标

v2 测试体系不再围绕“某 provider 是否写出了某个 session 文件”展开，而是围绕 agent-first 语义展开。

### 13.2 单元测试

重点覆盖：

- 配置解析
- agent 名冲突校验
- 保留关键字校验
- 项目解析规则
- `-r` 模式解析
- `-a` 权限解析
- `ccb ask` 语法解析
- workspace 规划
- runtime backend 选择
- per-agent queue policy
- restore 决策树
- provider capability 分派
- compatibility mode 解析与继承
- job contract 与 receipt 结构
- completion profile 选择
- completion detector contract
- completion source 事件规范化
- reply selector 终态选文规则
- 原子状态落盘

### 13.3 集成测试

重点覆盖：

- `ccb agent1 agent2` 启动多 agent
- 两个同 provider agent 并发启动
- agent attach 幂等行为
- `ccb ask` 的异步 job 流
- 单播 `submit -> job_id` 回执路径
- 广播 `submit -> submission_id + child job_ids` 回执路径
- `ccb ask all from agent1 ...` 的广播 fan-out 与 self-exclusion
- `ccb cancel <job_id>` 的 job 级取消路径
- `ccb pend <agent>` 与 `ccb pend <job_id>` 的区别
- `ccb watch <agent>` 与 `ccb watch <job_id>` 的区别
- `serial-per-agent` 队列行为
- `reject-when-busy` 行为
- askd 挂载后跨多次 `ccb ask` 持续复用
- provider 恢复成功路径
- provider 恢复失败后 checkpoint 回退路径
- `-a` 仅影响目标 agent，不污染其他 agent
- `ccb ping` / `ccb pend` / `ccb watch` 的 agent-first 观测路径
- Codex `task_complete` 驱动的精确完成路径
- Codex `turn_aborted` 驱动的取消/失败路径
- Codex tool follow-up 后才触发 turn completion 的路径
- Codex stop hook continuation 阻塞后继续运行直至 `task_complete` 的路径
- Gemini `stream-json result` 驱动的精确完成路径
- Gemini ACP `end_turn` 驱动的精确完成路径
- Gemini pane-backed `session_reply_stable` 驱动的 observed 完成路径
- Gemini 显式取消信息驱动的取消路径
- OpenCode 等 legacy provider 的 `CCB_DONE + quiet window` 兼容路径
- legacy provider 在 `doctor` / `ping` / `ps` 中暴露 `legacy completion mode`

### 13.4 系统测试

重点覆盖：

- askd crash 后重启恢复
- `mount_state=mounted` 且 askd 崩溃后的自动重拉起
- `mount_state=unmounted` 时 `ccb ask` / `pend` / `watch` 的硬失败路径
- 陈旧 pid / socket 清理
- 工作区损坏后的恢复策略
- git worktree 缺失或脏状态处理
- provider 进程无响应超时
- 大文本回复流式传输
- 多 agent 同时写事件流时的数据完整性
- history snapshot 导出与 handoff 审计
- 项目解析错误时的硬失败路径
- `ccb kill` 卸载 askd 与 `ccb kill -f` 全局清理的区别
- Codex rollout 日志切换、重绑、恢复后仍能准确识别 `task_complete`
- Codex 流重试或短暂断连后，未出现 `task_complete` 前不得提前完成
- 兼容模式关闭时，Codex idle quiet 不得被视为 completed
- Gemini session file 原地改写、短暂损坏、重试读取后的稳定识别
- Gemini `lastUpdated` / mtime 粒度不足时，force-read 仍能识别 reply 收敛
- Gemini 会话文件切换、project hash 重绑后仍能保持 anchor 归属正确
- 兼容模式关闭时，Gemini idle quiet 不得在无 `result` / `end_turn` / `reply_stable` 的情况下视为 completed
- legacy provider 在未升级 detector 前仍可工作，但其 `completion_confidence` 必须固定为 `degraded`
- legacy provider 迁移到新 detector family 后，旧 `legacy_text_quiet_detector` 可被无痛替换

### 13.5 回归测试矩阵

必须显式覆盖下列组合：

- `manual + fresh`
- `manual + provider`
- `manual + auto`
- `auto + fresh`
- `auto + provider`
- `auto + auto`

其中前者为权限模式，后者为恢复模式。

除此之外，至少还要覆盖以下 smoke 维度：

- `pane-backed + exact`
- `pane-backed + observed`
- `pane-backed + degraded`
- `headless + exact`
- `git-worktree + pane-backed`
- `inplace + pane-backed`

### 13.6 假 provider 测试框架

为了避免真实 CLI 不稳定影响核心回归，v2 应引入 fake provider adapter：

- 可控启动成功/失败
- 可控恢复成功/失败
- 可控延迟与流式输出
- 可控 crash 与半开状态

askd、restore、job/event 逻辑应主要依赖 fake adapter 做稳定测试。

建议继续细化为“事件脚本驱动”的 fake provider，而不是只返回静态假结果。

当前建议把 fake harness 做成一组 profile-aware provider alias，而不是单个 `fake`：

- `fake`
  - `structured_result` / exact 路径
- `fake-codex`
  - `protocol_turn` / exact 路径
- `fake-claude`
  - `session_boundary` / observed 路径
- `fake-gemini`
  - `anchored_session_stability` / observed 路径
- `fake-legacy`
  - `legacy_text_quiet` / degraded 路径

这样 askd / dispatcher / watch / pend 的主链路可以直接覆盖 exact / observed / degraded 三类完成族，而不必等真实 provider 全部接入后再补回归。

#### 13.6.1 统一事件脚本模型

每个 fake provider 测试用例应能声明一段事件脚本，例如：

```json
[
  {"t": 0, "type": "anchor_seen"},
  {"t": 20, "type": "assistant_chunk", "text": "hello"},
  {"t": 40, "type": "assistant_chunk", "text": " world"},
  {"t": 60, "type": "result"}
]
```

建议统一支持以下事件：

- `anchor_seen`
- `assistant_chunk`
- `tool_call`
- `tool_result`
- `result`
- `turn_aborted`
- `cancel_info`
- `error`
- `pane_dead`
- `session_snapshot`
- `session_mutation`
- `session_rotate`
- `sleep`

统一规则：

- `t` 表示相对时间，便于验证 timeout 与 settle window
- `session_snapshot` / `session_mutation` 用于模拟 Gemini 这类落盘观察 provider
- `result` / `turn_aborted` 用于模拟 Codex、Claude headless、Gemini structured 这类协议终态 provider
- 同一 fake adapter 要能配置 `capabilities`，从而覆盖 exact / observed / degraded 三种完成路径

#### 13.6.2 Gemini 专用假事件夹具

Gemini 相关测试应至少提供以下 fixture：

- `gemini_stream_result_success`
  - `assistant_chunk* -> result`
- `gemini_acp_end_turn_success`
  - `assistant_chunk* -> acp_stop(end_turn)`
- `gemini_pane_reply_stable_success`
  - `anchor_seen -> session_snapshot(reply=v1) -> session_mutation(reply=v2) -> stable_window_elapsed`
- `gemini_cancel_info`
  - `anchor_seen -> cancel_info`
- `gemini_session_corrupt_then_recover`
  - `anchor_seen -> parse_error -> parse_error -> session_snapshot(reply=ok)`
- `gemini_session_corrupt_fail`
  - `anchor_seen -> parse_error * N -> fail`
- `gemini_session_rotate`
  - `anchor_seen(old_session) -> session_rotate(new_session) -> re-anchor -> session_reply_stable`
- `gemini_pane_dead`
  - `anchor_seen -> pane_dead`
- `gemini_legacy_quiet`
  - `assistant_chunk -> quiet_timeout`
- `legacy_done_marker_success`
  - `assistant_chunk -> ccb_done_marker`
- `legacy_quiet_fallback_success`
  - `assistant_chunk -> quiet_timeout`

其中必须额外断言：

- `gemini_pane_reply_stable_success` 输出 `completion_confidence = observed`
- `gemini_stream_result_success` 与 `gemini_acp_end_turn_success` 输出 `completion_confidence = exact`
- `gemini_legacy_quiet` 仅在 compatibility mode 开启时允许通过
- `session_mutation` 会重置 `stable_since`
- `legacy_done_marker_success` 与 `legacy_quiet_fallback_success` 输出 `completion_confidence = degraded`
- legacy fixture 不得输出 `exact`

#### 13.6.3 断言模型

fake provider 测试不应只断言“最后返回文本正确”，还应断言：

- `completion_status`
- `completion_reason`
- `completion_confidence`
- `anchor_seen`
- `reply_started`
- `reply_stable`
- `job terminal timestamp`
- `event cursor monotonicity`

这样可以避免实现阶段再次退回“只看文本内容”的旧逻辑。

#### 13.6.4 Detector 独立测试原则

v2 中必须把 detector 测试与 adapter 测试拆开。

建议至少分三层：

- detector unit test
  - 直接喂入 `CompletionItem`
  - 不启动任何 provider runtime
- source normalization test
  - 验证 provider 原始输出如何转换为 `CompletionItem`
- adapter integration test
  - 只验证 adapter 是否正确装配 `source + detector + selector`

这样做的目的：

- detector 状态机可以快速、稳定回归
- source 解析错误不会和 detector 逻辑耦合在一起
- adapter 退化成编排层，更容易替换 provider

必须避免的旧问题：

- “跑一遍真 CLI，只看最后是否有回复”
- “adapter 自己偷偷补一个 timeout，然后测试也跟着过”
- “reply 选取逻辑和完成判定逻辑混在一起无法隔离”

#### 13.6.5 长时静默与长轮次稳定性测试

由于真实 LLM 执行可能持续很久且输出不连续，v2 必须把“长时静默”作为一等测试场景，而不是只测短回复。

至少覆盖：

- 长工具调用后 30 秒以上无新文本，但未出现 terminal event
- 多段 assistant 输出之间存在长静默，但最终仍继续回复
- `watch` client 中途断开后重新订阅，不丢 terminal decision
- `pend` 在 job 运行中反复读取，只看到 preview，不误判 completed
- `cancel` 发生在长静默窗口中，最终状态仍正确落到 `cancelled`

断言重点：

- exact detector 在无明确 terminal signal 时不得因 quiet window 提前完成
- observed detector 只能在满足稳定窗口条件后完成
- degraded detector 必须显式暴露 `completion_confidence=degraded`
- askd 在长轮次期间 heartbeat 不得中断，`doctor` 必须能持续看到该 job 仍在运行

## 14. 实施顺序

### 阶段 1：模型与文档

- 固化 CLI 语义
- 固化 agent 配置 schema
- 固化 restore / permission 模型
- 固化项目解析规则
- 固化 runtime backend 与 queue policy
- 固化数据布局与测试矩阵

### 阶段 2：核心库

- `agent_models`
- `agent_config`
- `agent_store`
- `job_store`
- `provider_catalog`
- `completion_models`
- `completion_source`
- `completion_detector_registry`
- `reply_selector`
- `workspace_manager`
- `project_resolver`
- `snapshot_manager`

建议阶段 2 再细分为以下顺序：

1. `completion_core`
   - 固定 `CompletionItem / Decision / State / Cursor / Profile / RequestContext`
   - 先落 `models.py` 与 `profiles.py`
2. `completion_detector_registry`
   - 先实现按 profile 装配 detector / selector 的最小工厂
   - 第一波不强求 `build_source()` 同时完成
3. `reply_selector`
   - 先实现 `structured_result`、`final_message`、`session_reply` 三类 selector
4. `completion_detectors`
   - 先落 `protocol_turn`
   - 再落 `structured_result`
   - 再落 `legacy_text_quiet`
   - 最后落 `anchored_session_stability`
5. `completion_orchestration`
   - 打通 `source -> detector -> selector -> decision`
   - 保持不依赖真实 provider、不读取 provider 私有文件
6. `provider_catalog`
   - 先固化 provider manifest、capability、runtime-mode 到 completion-profile 的映射
   - 明确 `Codex / Claude / Gemini / OpenCode / Droid` 的默认 completion family
7. `typed_store`
   - 固化 `agent_store / job_store / snapshot_store`
   - 路径统一绑定到 `.ccb/agents/` 与 `.ccb/askd/`
8. `workspace_manager`
   - 先做 `planner / binding / validator`
   - `git_worktree` 的真实执行留在后半段接入

阶段 2 的最小验收标准：

- 不依赖真实 provider，即可跑通 fake provider 的 exact / observed / degraded 三类 decision
- `CompletionDecision` 可稳定序列化到 snapshot / job store
- detector 可脱离 adapter 单测
- provider catalog 可按 `provider + runtime_mode` 稳定解析到 completion profile
- `.ccb/askd/`、`.ccb/agents/` 的核心落盘路径在 store 层中固定

建议再明确一个阶段 2 的“第一波”目标，避免范围继续膨胀：

- 第一波只实现：
  - `completion_core`
  - `completion_detectors`
  - `reply_selector`
  - `completion_orchestration`
  - `provider_catalog`
- 第一波不实现：
  - askd socket server
  - 真实 provider runtime 启停
  - tmux / WezTerm 编排
  - job queue 派发

### 阶段 3：askd v2

- 守护主循环
- agent registry
- 统一 job 协议
- per-agent queue
- health / restore / shutdown
- mount_state / ownership / stale cleanup

### 阶段 4：provider adapter 迁移

- 先接入 fake provider
- 再迁移 Claude / Codex / Gemini / OpenCode / Droid
- 逐个验证恢复、权限、watch 能力
- 逐个把 provider 迁移到对应 detector family，而不是在 adapter 内继续内联状态机

建议迁移拆分为：

1. `Codex`
   - 先验证 `protocol_turn_detector`
2. `Claude headless`
   - 验证 `structured_result_detector`
3. `Claude interactive`
   - 验证 `session_boundary_detector`
4. `Gemini structured`
   - 验证 `structured_result_detector`
5. `Gemini pane-backed`
   - 验证 `anchored_session_stability_detector`
6. `OpenCode / Droid / 其他`
   - 先挂 `legacy_text_quiet_detector`
   - 后续再逐步替换成新 detector

阶段 4 的迁移完成判据：

- adapter 内不再直接写完成状态机
- terminal result 必须来自 `CompletionDecision`
- `doctor` 能显示该 provider 当前使用的 detector family

### 阶段 5：CLI 重写

- 默认入口 `ccb [agent_names...] [-r] [-a]`
- `ask` / `kill` / `ps` / `logs` / `doctor`
- `ping` / `pend` / `watch`
- 清理旧 provider-first 命令路径

### 阶段 6：系统回归

- 并发场景回归
- 恢复场景回归
- 崩溃恢复回归
- 文档与 README 对齐

## 15. 基于当前进度的后续 5 步执行计划

以下 5 步不是抽象 roadmap，而是基于当前代码状态直接展开的执行顺序。

当前已完成的基础：

- v2 `start / ask / ping / pend / watch / cancel / kill / ps / doctor`
- `askd` socket server / dispatcher / tracker / snapshot 主链路
- fake provider 全套 completion family 测试基线
- 真实 `codex` execution adapter
- 真实 `claude` execution adapter
- `codex / claude / gemini` 的 start-time provider binding resolver

后续 5 步建议严格按下面顺序推进。

### 15.1 第一步：接入真实 Gemini execution adapter

目标：

- 把 `gemini` 从“只有 completion profile 与 binding”推进到“真实 execution adapter 可运行”
- 让 v2 首次具备 `codex / claude / gemini` 三个主 provider 的真实执行路径

实现范围：

- 新增 `lib/provider_execution/gemini.py`
- 在 `lib/provider_execution/registry.py` 注册 `GeminiProviderAdapter`
- 复用 `gaskd_session.load_project_session()`
- 复用 `gemini_comm.GeminiLogReader`
- 在 adapter 中输出标准 `CompletionItem`

最小实现要求：

- `start()` 能附着到已有 pane/session
- `poll()` 至少支持：
  - `ANCHOR_SEEN`
  - `SESSION_SNAPSHOT` 或 `SESSION_MUTATION`
  - `PANE_DEAD`
  - `ERROR`
- 不在 adapter 中直接写终态状态机
- 终态仍交给 `AnchoredSessionStabilityDetector`

验收标准：

- `gemini` 无 session 时保持 passive，不报错
- 有 session 时能产出 session-based item 流
- `dispatcher + tracker` 能把 job 推进到 `completed`

测试要求：

- `test_v2_execution_service.py`
  - passive without session
  - emits session snapshot items
  - reports pane dead
- `test_v2_askd_socket.py`
  - `askd + gemini adapter + tracker` 级联完成

### 15.2 第二步：补真实 provider 的 phase2 黑盒链路

目标：

- 不只测 adapter 单体和 socket 级联，还要锁住真实 CLI 子进程路径
- 让 `ccb -> askd -> execution -> tracker -> watch/pend` 形成完整黑盒回归

实现范围：

- 扩充 `test/test_v2_phase2_entrypoint.py`

优先补的黑盒场景：

1. `claude` real adapter
   - `start`
   - `ask`
   - `watch`
   - `pend`
2. `gemini` real adapter
   - `start`
   - `ask`
   - `watch`
   - `pend`
3. `watch <agent_name>` 与 `watch <job_id>` 两条路径都要覆盖

最小实现要求：

- 使用 monkeypatch/fake reader 驱动真实 adapter
- 不依赖真实 tmux、真实 CLI 二进制
- 断言最终输出文本，而不是只断言返回码

验收标准：

- `watch` 最终必须看到 `watch_status: terminal`
- `pend` 最终必须看到正确的：
  - `reply`
  - `completion_reason`
  - `completion_confidence`
- `doctor` 必须显示对应 completion family

测试要求：

- `test_ccb_claude_real_adapter_blackbox_watch_chain`
- `test_ccb_gemini_real_adapter_blackbox_watch_chain`

### 15.3 第三步：统一 provider runtime binding 与 start/attach 语义

目标：

- 把目前“start 时解析 binding”的能力继续向运行时语义收敛
- 明确 `provider_runtime_ref / provider_session_ref / workspace_path` 三者在整个生命周期中的不变量

实现范围：

- `lib/cli/services/provider_binding.py`
- `lib/cli/services/start.py`
- `lib/askd/services/runtime.py`
- 必要时新增 `lib/provider_execution/runtime_binding.py`

需要补齐的点：

- `attach()` 后 runtime.json 的字段含义写清楚并固定
- `restore()` / `ensure_ready()` 不再退回模糊占位值
- session rotate 后是否更新 `provider_session_ref`，要形成统一策略
- `doctor` 与 `ps` 输出要能反映真实 binding，而不是只显示 provider 名

建议策略：

- `provider_runtime_ref`
  - 优先表示真实 pane/runtime identity
- `provider_session_ref`
  - 优先表示真实 provider session id
  - 没有 session id 时退回 session path
- rotate 时先只更新 job snapshot/state，不立即重写 runtime.json
  - 避免运行中 runtime identity 与 job-level turn identity 混杂

验收标准：

- `start / restore / ensure_ready` 三条路径字段语义一致
- 不同 provider 的 runtime.json 结构稳定
- `doctor` 可以准确展示 provider binding 来源

测试要求：

- `test_v2_phase2_entrypoint.py`
  - start/restore binding consistency
- `test_v2_askd_socket.py`
  - attach/restore roundtrip with real refs
- `test_v2_askd_dispatcher.py`
  - runtime context consistency assertions

### 15.4 第四步：补 OpenCode / Droid 的 v2 adapter 占位迁移

目标：

- 把第一阶段核心 provider 覆盖补齐，不让 v2 长期停留在“只有三家真实 provider”
- 即使完成检测先用 degraded/fallback，也要先统一进入 v2 adapter 架构

实现范围：

- `lib/provider_execution/opencode.py`
- `lib/provider_execution/droid.py`
- `lib/provider_execution/registry.py`

第一波要求：

- 只做最小可运行迁移
- completion family 先挂当前文档既定策略：
  - 优先 `legacy_text_quiet`
  - 后续再升级为更强结构化检测

adapter 最小职责：

- session 加载
- pane 可用性检查
- prompt 注入
- 文本事件转标准 `CompletionItem`
- `PANE_DEAD / ERROR` 终态输入

明确不在这一波做的事：

- 不追求完美 reply 质量
- 不在 adapter 内做 provider 私有补锅状态机
- 不在第一波接入复杂 session rotate 恢复

验收标准：

- provider 已能通过 v2 `askd` 主链路运行
- `watch` / `pend` 至少可读
- 失败时状态要可解释，不能静默挂起

测试要求：

- execution 单测
- socket 级联
- 至少一条 phase2 黑盒 smoke 测试

### 15.5 第五步：第一阶段稳定性封板与文档收口

目标：

- 在进入更大范围功能扩展前，把第一阶段做成一个可验收的稳定基线
- 固化测试矩阵、诊断文档和风险边界

实现范围：

- `docs/agent-first-v2-architecture.md`
- `README.md`
- `test/` 回归矩阵
- 必要时补 `doctor` / `ps` 输出说明

需要完成的收口项：

1. 测试矩阵整理
   - unit
   - socket integration
   - phase2 blackbox
   - long-running / silent-gap scenarios
2. 文档同步
   - 当前已实现 provider
   - 当前未实现 provider
   - 当前 completion family 映射
3. 诊断约束
   - `doctor` 输出规范
   - `pend/watch` 语义边界
4. 风险清单
   - 长静默误判
   - session rotate 一致性
   - stale runtime binding
   - pane death recovery

封板验收标准：

- 主路径 provider:
  - `codex`
  - `claude`
  - `gemini`
  已具备真实 adapter + 回归覆盖
- 次路径 provider:
  - `opencode`
  - `droid`
  至少进入 v2 adapter 架构
- 全量测试保持稳定通过
- 文档中的“已实现 / 未实现 / 风险”与代码状态一致

建议封板时必须执行的测试命令：

```bash
pytest -q
pytest -q test/test_v2_execution_service.py test/test_v2_askd_socket.py test/test_v2_phase2_entrypoint.py
```

若要进入下一阶段，必须先满足：

- 没有新增巨石文件
- provider adapter 边界保持纯粹
- completion 决策仍统一由 tracker/detector 主导
- phase2 黑盒测试对主 provider 至少各有一条稳定链路

### 15.6 当前落地状态（第一阶段已完成）

截至当前代码状态，前述 5 步已经按第一阶段目标落地到 `../ccb_source`。

已实现的核心命令：

- `ccb [agents...]`
- `ccb ask <agent_name> [from <sender>] <message>`
- `ccb ping <agent_name>`
- `ccb pend <agent_name|job_id>`
- `ccb watch <agent_name|job_id>`
- `ccb cancel <job_id>`
- `ccb kill`
- `ccb ps`
- `ccb doctor`

已接入的 provider execution adapter：

- `codex`
  - 真实 adapter
  - completion family: `protocol_turn`
- `claude`
  - 真实 adapter
  - completion family: `session_boundary`
- `gemini`
  - 真实 adapter
  - completion family: `anchored_session_stability`
- `opencode`
  - v2 最小 adapter
  - completion family: `legacy_text_quiet`
- `droid`
  - v2 最小 adapter
  - completion family: `legacy_text_quiet`

当前 `doctor / ps` 诊断输出已补齐的字段：

- `provider_runtime_ref`
- `provider_session_ref`
- `workspace_path`
- `binding_status`

也就是：

- `ps` 不再只显示 `agent/provider/state`
- `doctor` 不再只显示 `agent/provider/completion_family`
- 现在可以直接看到该 agent 当前到底绑定到了哪个 pane/runtime、哪个 provider session、哪个 workspace

当前第一阶段测试矩阵：

- unit
  - completion detector / selector / snapshot / registry / config loader
- execution adapter
  - `test_v2_execution_service.py`
- socket integration
  - `test_v2_askd_socket.py`
- phase2 blackbox
  - `test_v2_phase2_entrypoint.py`

已补上的关键回归：

- `GeminiProviderAdapter` 的 passive / snapshot / pane-dead 路径
- `AskdApp + gemini adapter + tracker` 级联 observed completion
- `claude` real adapter 的 `start -> ask -> pend -> watch(job_id|agent)` 黑盒链路
- `claude` real adapter 支持无 `CCB_DONE` 的 `turn_duration` 主完成路径
- `codex` real adapter 支持结构化 `task_complete / turn_aborted`
- `gemini` real adapter 的 `start -> ask -> pend -> watch(job_id|agent)` 黑盒链路
- `opencode / droid` 的 v2 adapter 最小 smoke
- `attach` 重复调用后 runtime binding 字段刷新
- `start -r` 后 runtime.json 保持真实 binding refs
- runtime binding 生命周期语义已收敛为统一小模块
- `doctor / ps` 不再依赖占位 provider ref，而是输出 `bound / partial / unbound`
- `watch / pend` 在 askd 代际切换后的首次 socket 失败下可自动重连
- `get / watch` 已暴露 askd generation，便于诊断挂载代际
- 修复了 terminal snapshot 可能被 pending tracker 视图回写覆盖的竞态
- `ping askd` 在 stale mount 下可自动拉起新 askd 并提升 generation
- `doctor` 已输出 `askd_generation`

第一阶段仍明确保留的风险边界：

- `claude` 当前主路径已支持 `turn_duration` 结构化完成，但 `CCB_DONE` fallback 仍保留，尚未完全退出实现
- `gemini` 当前使用 `anchored_session_stability`，强依赖 session 快照稳定窗口，长静默误判仍需继续做 soak 测试
- `opencode / droid` 当前只完成 v2 adapter 迁移，不追求最终 reply 质量与最强结构化完成检测
- session rotate 的 runtime.json 重写策略仍保持保守，不把 job-level turn identity 混入 runtime identity

当前建议作为第一阶段封板验收的命令：

```bash
pytest -q
pytest -q test/test_v2_execution_service.py test/test_v2_askd_socket.py test/test_v2_phase2_entrypoint.py
```

### 15.7 第一阶段之后的后续计划

第一阶段已经完成“agent-first 主链路可运行、主 provider 可观测、统一 askd 可闭环”的目标。

后续计划不应再以“继续补命令”为主，而应转入以下重点：

- 提升主 provider 的完成信号精度
- 收敛 runtime binding 的生命周期语义
- 把 askd 守护稳定性做成硬约束
- 把 legacy provider 从“已接入”推进到“更可信”

建议严格按下面顺序推进。

#### 15.7.1 第二阶段第一步：升级 Claude 完成识别

这是后续最高优先级。

原因：

- 当前 `claude` real adapter 仍依赖 prompt 级 `CCB_DONE`
- 这会把 provider 完成语义继续绑在 prompt 约束上
- 文档中已经明确，这不是最终最优终态信号

目标：

- 把 `ClaudeProviderAdapter` 从“文本 done-marker 驱动”升级为“结构化事件驱动”
- 主完成信号不再默认依赖 `CCB_DONE`
- subagent 活动只用于活跃度观察，不再直接参与主完成判定

实现范围：

- `lib/provider_execution/claude.py`
- `lib/claude_comm.py`
- 必要时补 `lib/completion/detectors/session_boundary.py`

实施原则：

- 主会话日志必须保留结构化字段，而不是只抽取 `(role, text)`
- `turn_duration` 或等价主会话边界应进入主判定链路
- `CCB_DONE` 只保留为 compatibility fallback
- 不允许把 subagent 最终文本直接当作主 turn 完成

验收标准：

- 没有 `CCB_DONE` 时，交互式 `claude` 主路径仍可完成
- `watch` / `pend` 的 `completion_reason` 能区分：
  - `turn_duration`
  - `pane_dead`
  - `api_error`
  - `legacy_quiet`
- subagent 活跃但主会话未收尾时，不得提前 completed

测试要求：

- `test_v2_execution_service.py`
  - 无 `CCB_DONE` 的主会话完成路径
- `test_v2_askd_socket.py`
  - `claude` session-boundary 结构化完成
- `test_v2_phase2_entrypoint.py`
  - `claude` real adapter blackbox 在无 `CCB_DONE` 条件下通过

#### 15.7.2 第二阶段第二步：Codex exact completion 已落地

优先级仅次于 `claude`。

结果：

- `codex` 主路径已经收敛到官方 turn 级结构化完成
- 终态判断不再依赖 prompt 级 `CCB_DONE`

当前实现：

- 让 `codex` 主路径使用结构化 `task_complete / turn_aborted`
- `final_answer` 只参与 reply 选择，不参与终态判断
- `CCB_DONE` 已退出主完成链路，仅保留为旧历史文本清洗与显式兼容兜底

实现范围：

- `lib/provider_execution/codex.py`
- `lib/codex_comm.py`
- 必要时补 `protocol_turn` detector 的元数据使用方式

已完成点：

- `CodexProviderAdapter` 已切换到结构化 entry 路径，而不是继续只读 `(role, text)`
- `task_complete / turn_aborted / final_answer` 已进入 askd 主判定链路
- `TURN_BOUNDARY` 由真实 turn terminal event 触发，而不是由 `CCB_DONE` 文本触发
- 这使当前 `codex` 终态判断与 `9.4 Codex 完成识别规范` 保持一致

落地原则：

- `Codex` 的 completed / cancelled / failed 必须由结构化 turn 终态事件决定
- `CCB_REQ_ID` 只负责锚定本轮 ask，不负责声明完成
- `final_answer` 只负责 reply 选择，不负责终态判断
- `CCB_DONE` 退出默认主路径，只能在显式 compatibility mode 下保留
- `idle quiet` 不得再作为默认 completed 路径，只能作为降级兜底并显式标记 `degraded`

事件模型要求：

- `CodexLogReader` 必须从 JSONL 中暴露结构化 entry，而不是只暴露 `(role, text)`
- 新接口建议与 `claude` 对齐，至少提供：
  - `try_get_entries(state)`
 - legacy askd adapter 也应优先消费 `wait_for_entries(state, timeout)`，不再把 `CCB_DONE` 作为主完成协议
  - `wait_for_entries(state, timeout)`
- 每条结构化 entry 至少包含以下字段：
  - `entry_type`
  - `payload_type`
  - `role`
  - `text`
  - `phase`
  - `turn_id`
  - `task_id`
  - `last_agent_message`
  - `reason`
  - `entry`
- 若底层日志格式在不同版本 Codex 上存在差异，字段缺失时必须保留原始 `entry`，由 adapter 再做兼容解析，而不是在 reader 中直接吞掉

本轮 ask 的绑定规则：

1. 发送请求前记录日志基线 offset
2. 使用带 `CCB_REQ_ID` 的 prompt 提交本轮 ask
3. 读取发送后出现的结构化 `user` entry，确认其中包含本轮 `CCB_REQ_ID`
4. 当 `CCB_REQ_ID` 被观察到后，才将后续 assistant / protocol entry 纳入本轮 turn 跟踪
5. 若日志提供明确 `turn_id` / `task_id`，必须在 anchor 成功后把 `req_id -> turn_id` 绑定落到 runtime state
6. 若在配置时限内只看到 assistant 文本、但没有 anchor，不得把该文本误归属于当前 ask

状态机要求：

- `submitted`
  - 已下发 prompt，尚未确认 anchor
- `anchored`
  - 已观察到带 `CCB_REQ_ID` 的 user turn
- `streaming`
  - 已接收到当前 turn 的 assistant 文本或协议事件
- `completed`
  - 收到 `task_complete`
- `cancelled`
  - 收到 `turn_aborted` 且原因是 interrupt / user cancel / abort
- `failed`
  - 收到 `turn_aborted` 且原因是 error / execution failure / protocol failure

终态映射规则：

- `task_complete`
  - 产出 `TURN_BOUNDARY`
  - `completion_status = completed`
  - `completion_reason = task_complete`
  - `completion_confidence = exact`
- `turn_aborted`
  - 产出终态 item，映射到 `cancelled` 或 `failed`
  - `completion_reason = turn_aborted`
  - `completion_confidence = exact`
- `pane_dead`
  - 仅在 pane 确认死亡时触发
  - 仍保留为 transport/runtime 级终态，而不是协议终态
- `legacy_quiet` / `legacy_done_marker`
  - 只允许在显式 compatibility mode 下启用
  - 必须强制标记 `completion_confidence = degraded`

reply 选择顺序：

1. `task_complete` 中的 `last_agent_message`
2. 同一 turn 内 `phase = final_answer` 的最后一条 assistant message
3. 同一 turn 内最后一条 assistant message
4. 若以上都缺失，则保留空 reply，但仍允许按 `task_complete` 正常 completed

实现拆分建议：

第一步：升级 `lib/codex_comm.py`

- 保留现有 `try_get_event()` 作为过渡兼容接口
- 新增结构化 entry 读取接口，不再只抽取 message text
- 抽出 entry 规范化逻辑，把 `response_item`、`event_msg`、其他兼容 entry 类型统一映射成公共结构
- 明确区分：
  - user anchor entry
  - assistant content entry
  - turn lifecycle entry
  - terminal entry

第二步：升级 `lib/provider_execution/codex.py`

- adapter 从“文本匹配状态机”切换到“结构化 turn 状态机”
- runtime_state 至少增加：
  - `anchor_seen`
  - `bound_turn_id`
  - `bound_task_id`
  - `last_agent_message`
  - `last_final_answer`
  - `last_assistant_message`
  - `compatibility_mode`
- `reply_buffer` 继续保留，但只做展示缓冲，不再承担 completed 判定职责
- `TURN_BOUNDARY` 必须由 `task_complete` 触发，而不是由 `CCB_DONE` 触发

第三步：收敛 completion detector 元数据

- `protocol_turn` detector 需要正确消费：
  - `completion_status`
  - `completion_reason`
  - `completion_confidence`
  - `turn_id`
  - `anchor_seen`
- `watch` / `pend` / `doctor` 输出必须能直接看出 `codex` 已进入 exact completion mode
- `ps` / `doctor` 若运行在 compatibility mode，必须显式标出 degraded

第四步：保留可控回退，但默认关闭

- compatibility mode 只为旧版日志格式或异常环境保底
- 默认配置下不启用 `CCB_DONE` fallback
- 若必须启用，必须通过明确开关进入，并在诊断输出中暴露

验收标准：

- `completion_confidence = exact`
- `completion_reason` 至少能区分：
  - `task_complete`
  - `turn_aborted`
  - `pane_dead`
  - `legacy_quiet`
- 不再因为 assistant 暂时静默或出现 `final_answer` 就提前 completed
- `task_complete` 但没有 `CCB_DONE` 时，`watch` / `pend` 仍可正确收口
- `turn_aborted` 能稳定区分取消与失败，不把 aborted 一律当作 completed
- `doctor` / `ps` 能显示当前 `codex` 使用的是 `exact completion mode` 还是 `compatibility mode`

测试要求：

- execution 单测：
  - `task_complete` 正常 completed
  - `turn_aborted` -> cancelled
  - `turn_aborted` -> failed
  - 无 `CCB_DONE`、仅靠结构化终态仍能完成
  - 有 `final_answer` 但未见 `task_complete` 时不得提前 completed
  - assistant 长静默后继续 follow-up tool turn，不得误判完成
- socket integration：
  - 覆盖 `completed / failed / cancelled`
  - 覆盖 `watch(job_id)` 与 `watch(agent_name)` 的终态输出
  - 覆盖 `pend` 在 exact mode 下读取最终 reply
  - 覆盖 compatibility mode 的 `degraded` 标记
- phase2 blackbox：
  - 真实 `codex` adapter 路径在无 `CCB_DONE` 条件下通过
  - `task_complete` 能驱动 `watch` 收口
  - `turn_aborted` 能驱动外层 job 状态进入正确终态

落地完成后的预期收益：

- `codex` 终态语义与官方 turn 生命周期一致
- 不再依赖 prompt 记忆是否输出 `CCB_DONE`
- 对 tool continuation、长时静默、流式重试更稳
- askd 可以把 `codex` 纳入与 `claude` / `gemini` 同一套 completion 诊断模型

回退策略：

- 若某些 `codex` 版本缺少稳定 `task_complete / turn_aborted`，不回退整个 v2 架构
- 仅对该 provider 打开局部 compatibility mode
- compatibility mode 必须保留显式告警，后续再按版本继续收缩

#### 15.7.3 第二阶段第三步：对 Gemini 做 soak 与静默场景封板

`gemini` 当前不应立刻继续重构，而应先做稳定性验证。

原因：

- `gemini` 已进入真实 adapter
- 当前主要风险不是“没有主链路”，而是 `anchored_session_stability` 在长静默场景中的误判边界

目标：

- 验证 `GeminiProviderAdapter` 在长时静默、session rotate、session lag 下的行为
- 先把 observed completion 做稳，再决定是否继续升级 structured mode

实现范围：

- `test/test_v2_execution_service.py`
- `test/test_v2_askd_socket.py`
- `test/test_v2_phase2_entrypoint.py`
- 必要时新增 soak/fault-injection 测试文件

必须补的场景：

- long silent gap
- session rotate during reply
- pane 存活但 session 落盘滞后
- `pend` 运行中反复读取，不误判 completed
- `watch` 中途断开后重新订阅，不丢 terminal decision

验收标准：

- 长静默不提前 completed
- reply 稳定窗口到达后再 completed
- rotate 后仍能继续跟踪正确 session
- `pend` / `watch` 结果一致

#### 15.7.4 第二阶段第四步：收敛 runtime binding 生命周期语义（已完成）

这一项是框架收敛，不是 provider 特性。

原因：

- 当前 `provider_runtime_ref / provider_session_ref / workspace_path` 已可输出
- 但它们的生命周期规则还没有完全被单独抽象

目标：

- 把 binding 规则从零散 service 中抽出，形成清晰的小模块
- 统一 `start / attach / restore / ensure_ready / doctor / ps` 对 binding 的理解

实际落地范围：

- `lib/cli/services/provider_binding.py`
- `lib/askd/services/runtime.py`
- `lib/agents/runtime_binding.py`

已落地结果：

- 新增统一 `RuntimeBinding` 小模块，集中负责：
  - 字段标准化
  - merge 规则
  - `bound / partial / unbound` 判定
- `attach / restore / ensure_ready` 不再生成假的：
  - `provider_runtime_ref`
  - `provider_session_ref`
- `doctor / ps` 统一消费同一套 binding 语义
- `dispatcher` 继续从 runtime 持久化记录向 execution adapter 透传最新 binding
- `restore checkpoint` 不再误写成 `provider_session_ref`

要固定的不变量：

- `provider_runtime_ref`
  - 表示真实 pane/runtime identity
- `provider_session_ref`
  - 表示真实 provider session identity
- `workspace_path`
  - 表示 agent 当前真实工作区

当前验收结果：

- `start / restore / ensure_ready / attach` 四条路径字段语义一致
- `doctor / ps` 输出不再出现“状态正确但 binding 显示占位值”
- session rotate 不把 job-level turn identity 写回 runtime identity

已补测试：

- `test_v2_askd_socket.py`
  - repeated attach refreshes refs without corrupting health
  - attach without provider binding does not synthesize refs
- `test_v2_phase2_entrypoint.py`
  - start/restore binding consistency
  - unbound start now reports `binding_status=partial`
- `test_v2_askd_dispatcher.py`
  - runtime context still matches persisted refs

当前状态：

- 该项可以视为第二阶段已完成事项，不再是待实现计划

#### 15.7.5 第二阶段第五步：做 askd 守护稳定性与代际测试

这一项是第一阶段之后最重要的系统性工作。

原因：

- provider adapter 进入主链路后，剩余风险将更多集中在 askd 本身
- 如果 askd 的挂载、接管、watch 重连不稳，provider 再精确也没有意义

目标：

- 把 askd 的持续挂载、heartbeat、generation takeover、watch reconnect 做成硬保证

实现范围：

- `lib/askd/app.py`
- `lib/askd/services/mount.py`
- `lib/askd/services/ownership.py`
- `lib/askd/socket_server.py`
- `lib/askd/socket_client.py`

必须覆盖的场景：

- askd 代际切换
- stale mount 自动接管
- watch client 从 cursor 重新订阅
- 长作业 heartbeat 持续刷新
- mount_state 与 socket 健康不一致时的恢复路径

验收标准：

- `mount_state=mounted` 但进程消失时，下次 `ask` / `ping` 能恢复
- `watch` 在 generation 切换后能感知并重新订阅
- 长作业期间 `doctor` 能持续显示 askd 健康
- 状态落盘顺序不出现 completed 但无 terminal decision 的矛盾状态

当前已落地的第一步：

- `watch` CLI 在 `AskdClientError` 后会重新连接当前项目 askd，并从原 cursor 继续
- `pend` CLI 在首次 socket 错误后会重新连接并重试一次
- `get / watch` handler 已返回 `generation`
- `doctor` phase2 输出已增加 `askd_generation`
- 修复 `dispatcher.complete / cancel` 中 tracker finish 晚于 snapshot 写入导致的竞态覆盖
- phase2 黑盒已覆盖 stale mount -> automatic takeover -> generation bump

已补测试：

- `test_v2_cli_watch_reconnect.py`
  - watch reconnect after first socket failure
  - pend reconnect after first socket failure
- `test_v2_askd_socket.py`
  - `get / watch` payload includes generation
- `test_v2_phase2_entrypoint.py`
  - `ping askd` recovers from stale mount and bumps generation
- 全量回归：
  - `pytest -q`
  - `412 passed`

当前已继续落地到后续 5 步的实现：

- 长作业 heartbeat 已有 blackbox：
  - 运行中的 fake job 会持续刷新 lease heartbeat
  - `doctor` 在运行期间可稳定看到 `askd_health=healthy`
- `watch` 已补强为 cursor 连续性回归：
  - generation 切换后的重连会沿用旧 cursor
  - 不重复消费已返回事件
- ownership 不一致矩阵已补齐核心判定：
  - `healthy / degraded / stale`
  - `takeover_allowed`
- terminal snapshot durability 已补强：
  - terminal snapshot 不再接受非 terminal tracker 视图回写
- askd 稳定性诊断已进入用户可见输出：
  - `ping askd`
  - `doctor`

下面 5 步的功能计划：

##### 15.7.5.2 第二步：补长作业 heartbeat 与 `doctor` 持续可见性黑盒

目标：

- 证明 askd 在长作业期间会持续刷新 lease heartbeat
- 证明 `ccb doctor` 在长作业执行中能稳定读到：
  - `askd_state=mounted`
  - `askd_health=healthy`
  - `askd_generation`

实现范围：

- `lib/askd/app.py`
- `lib/askd/services/mount.py`
- `lib/cli/services/doctor.py`
- `test/test_v2_phase2_entrypoint.py`

建议实现：

- 使用可控延迟的 fake provider 或长静默 provider 场景
- 在 job 运行期间反复调用 `doctor`
- 校验 lease `last_heartbeat_at` 发生推进，而不是只看进程仍然存活

验收标准：

- 长作业持续至少一个 heartbeat 周期后，`last_heartbeat_at` 明确推进
- `doctor` 在运行期不出现：
  - `askd_health=stale`
  - `askd_state=unmounted`
- job 完成后 heartbeat 仍保持一致，不出现 lease 回退

测试要求：

- `test_v2_phase2_entrypoint.py`
  - long-running ask keeps doctor healthy
- 必要时补：
  - `test_v2_askd_mount_ownership.py`
  - heartbeat freshness edge cases

当前状态：

- 已完成第一轮落地
- 已补 blackbox：
  - long-running fake job keeps heartbeat moving
  - doctor stays healthy during running job

##### 15.7.5.3 第三步：补 `watch` 跨 generation 重订阅端到端黑盒

目标：

- 证明 `watch` 不只是“第一次失败会重连”
- 而是在 askd 发生真实 generation 切换时，仍能从旧 cursor 继续收口到 terminal

实现范围：

- `lib/cli/services/watch.py`
- `lib/askd/handlers/watch.py`
- `lib/askd/services/dispatcher.py`
- `test/test_v2_phase2_entrypoint.py`

建议实现：

- 启动一个会延迟完成的 job
- watch 开始后人为制造 askd 代际切换：
  - 旧 askd 退出
  - lease 进入 stale
  - 新 askd 被 `connect_mounted_daemon()` 接管
- watch 继续从原 cursor 拉取，并最终看到 terminal batch

验收标准：

- watch 在 generation 切换后不丢 job
- 不重复输出已经消费过的事件
- 最终 terminal batch 中：
  - `job_id` 正确
  - `status` 正确
  - `reply` 正确

测试要求：

- `test_v2_phase2_entrypoint.py`
  - watch survives generation takeover
- 保留现有：
  - `test_v2_cli_watch_reconnect.py`
  - 作为轻量 socket-error 回归

当前状态：

- 已完成当前架构下的第一轮实现
- 已补强单测：
  - reconnect after socket error
  - cursor continuity across generation switch
- 说明：
  - 当前 askd 已补上 active execution persistence skeleton
  - `fake` provider 已支持 askd 重启后的 execution resume 黑盒
  - 真实 provider 仍未逐个接入 resume / rebind，因此目前不是“所有 provider 都可热接管”
  - 现阶段已保证：
    - watch 重连与 cursor 连续性
    - fake execution 在 askd 重启后继续完成
    - terminal decision 在 provider 已完成但 dispatcher 尚未 complete 的窗口内可恢复

##### 15.7.5.4 第四步：补 mount_state / pid / socket / heartbeat 不一致矩阵

目标：

- 把“守护看起来挂着，但实际不可用”的灰区状态收敛成明确规则
- 避免 CLI 在 degraded / stale 边界上表现摇摆

实现范围：

- `lib/askd/services/ownership.py`
- `lib/cli/services/daemon.py`
- `test/test_v2_askd_mount_ownership.py`
- `test/test_v2_phase2_entrypoint.py`

需要覆盖的组合：

- pid alive + socket dead + heartbeat stale
- pid alive + socket dead + heartbeat fresh
- pid missing + socket exists
- mount_state=mounted 但 lease/socket 文件不一致

预期策略：

- 只有明确满足 takeover 条件时才接管
- `degraded` 与 `stale` 必须继续严格区分
- `ping / ask / pend / watch` 对同一 lease 状态给出一致决策

验收标准：

- 不会把 healthy lease 误判成可接管
- 不会把 stale lease 长时间卡在 unavailable
- `ping askd` 与 `connect_mounted_daemon()` 的判定语义一致

测试要求：

- `test_v2_askd_mount_ownership.py`
  - ownership matrix
- `test_v2_phase2_entrypoint.py`
  - degraded vs stale CLI behavior

当前状态：

- 已完成核心矩阵判定补齐
- 已补测试：
  - fresh heartbeat + socket dead -> `degraded`
  - stale heartbeat + socket dead -> `stale`
  - healthy lease blocks takeover
  - stale lease allows takeover

##### 15.7.5.5 第五步：补 terminal state durability 与事件顺序硬保证

目标：

- 确保 job 终态一旦写入，不会被旧 tracker 视图、重复 poll、重连 watch 覆盖
- 确保 `watch / pend / get` 看到的 terminal 信息彼此一致

实现范围：

- `lib/askd/services/dispatcher.py`
- `lib/askd/services/snapshot_writer.py`
- `test/test_v2_askd_socket.py`
- `test/test_v2_askd_dispatcher.py`

需要重点验证：

- completed 后 snapshot 不被 pending state 回写
- cancelled / failed 的 terminal decision 不被后续 poll 覆盖
- repeated watch/get 在 terminal 后返回稳定结果

验收标准：

- terminal snapshot 单调稳定
- terminal event 顺序固定为：
  - `completion_terminal`
  - `job_completed / job_cancelled / job_failed`
- `pend / get / watch` 返回的：
  - `status`
  - `reply`
  - `completion_reason`
  - `completion_confidence`
  保持一致

测试要求：

- `test_v2_askd_socket.py`
  - terminal snapshot stability after completion
- `test_v2_askd_dispatcher.py`
  - no terminal overwrite on repeated poll

当前状态：

- 已完成第一轮落地
- 已修复：
  - `complete / cancel` 中 tracker finish 晚于 terminal snapshot 写入的竞态
  - terminal snapshot 被非 terminal tracker view 回写覆盖的问题
  - execution state 在 provider 已给出 terminal decision 后不再提前删除
  - askd 重启时可从 persisted terminal decision 恢复并继续收口 terminal job
- 已补测试：
  - repeated `get / watch` terminal stability
  - dispatcher ignores non-terminal tracker overwrite after terminal
  - terminal-pending execution restore

##### 15.7.5.7 第七步：补 active execution persistence / restart handover 骨架

目标：

- 为 askd 重启后的 execution 恢复建立独立、纯粹、可扩展的状态层
- 把“运行中 execution”与“completion snapshot / job store”从职责上分开
- 先用 `fake` provider 跑通恢复链路，再为真实 provider 后续接入留稳定接口

实现范围：

- `lib/provider_execution/state_models.py`
- `lib/provider_execution/state_store.py`
- `lib/provider_execution/service.py`
- `lib/provider_execution/fake.py`
- `lib/askd/app.py`
- `lib/askd/services/dispatcher.py`
- `test/test_v2_execution_service.py`
- `test/test_v2_phase2_entrypoint.py`
- `test/test_v2_askd_dispatcher.py`

已实现能力：

- `.ccb/askd/executions/` 下独立保存 active execution state
- state 中保存：
  - serializable `ProviderSubmission`
  - runtime context
  - `resume_capable`
  - `pending_decision`
- `ExecutionService.start/poll/finish/cancel` 已接入 persistence lifecycle
- `AskdApp.start()` 会触发 running jobs restore
- `dispatcher.restore_running_jobs()` 具备三种分支：
  - restore success -> 继续运行
  - terminal pending recovered -> 直接 complete
  - unrecoverable -> 明确收口为 `incomplete`
- `fake` provider 已实现：
  - `export_runtime_state()`
  - `resume()`

当前边界：

- 当前只对 `fake` provider 完成真正的 resume 验证
- `claude / codex / gemini / opencode / droid` 仍默认走：
  - 持久化最小 envelope
  - restart 后若无 provider-level resume，则 `requires_resubmit`
- 当前尚未持久化“未消费 completion items batch”，因此 crash 点若发生在 event append 之前，恢复后只能保证 terminal 收口，不保证完整重放中间 item

验收标准：

- active execution state 不与 snapshot/job store 混写
- fake 长作业在 askd 重启后可继续完成
- provider 已给出 terminal decision 时，restart 后不应误收口为 `requires_resubmit`
- unrecoverable execution 必须被明确降级为 terminal，不允许长期停留在假 `running`

测试要求：

- `test_v2_execution_service.py`
  - persist + resume fake submission
  - recover terminal pending decision
  - abandon non-resumable submission
- `test_v2_askd_dispatcher.py`
  - restore failure becomes incomplete terminal job
- `test_v2_phase2_entrypoint.py`
  - fake execution survives askd restart

##### 15.7.5.6 第六步：收敛 askd 稳定性诊断输出并作为第二阶段封板前置条件

目标：

- 把 askd 的稳定性信息从“内部判断”变成“用户可见”
- 让第二阶段后续 provider 工作都建立在已验证的守护稳定性之上

实现范围：

- `lib/cli/services/ping.py`
- `lib/cli/services/doctor.py`
- `lib/cli/phase2.py`
- `docs/agent-first-v2-architecture.md`

需要补齐的诊断面：

- `askd_generation`
- lease 健康原因
- socket/heartbeat/pid 的核心判定摘要
- 当前是否发生过 generation takeover

验收标准：

- `ping askd` 与 `doctor` 能快速判断：
  - 当前是否 healthy
  - 是否发生了代际切换
  - 是否仍存在恢复风险
- 完成本步后，才进入 `15.7.6 OpenCode / Droid observed completion` 深化阶段

测试要求：

- `test_v2_phase2_entrypoint.py`
  - doctor/ping expose askd stability fields
- 文档同步：
  - 把 askd 稳定性作为第二阶段封板前置条件写清楚

当前状态：

- 已完成第一轮落地
- 当前已输出的 askd 诊断字段包括：
  - `askd_generation`
  - `askd_last_heartbeat_at`
  - `askd_pid_alive`
  - `askd_socket_connectable`
  - `askd_heartbeat_fresh`
  - `askd_takeover_allowed`
  - `askd_reason`
- `ping askd` 也已输出对应稳定性字段

#### 15.7.8 基于当前进度的未来 5 步执行计划

下面 5 步以“先把真实 provider 恢复链路做扎实，再把 crash window 收窄，再做封板”作为顺序原则。
不建议跳步，否则很容易把问题重新堆回 askd 层。

##### 15.7.8.1 第一步：优先打通 Codex 的真实 execution resume

目标：

- 把 `codex` 从“restart 后只能 requires_resubmit”升级为“可在 askd 重启后继续完成”
- 先选 Codex，是因为其完成信号最结构化，恢复边界最清晰

原因：

- `codex` 已有较明确的 `task_complete / turn_aborted` 事件
- 相比 `claude / gemini`，Codex 的 turn 结束判定更稳定，适合作为第一个真实 provider 样板

实现范围：

- `lib/provider_execution/codex.py`
- `lib/provider_execution/service.py`
- `lib/provider_execution/state_models.py`
- `test/test_v2_execution_service.py`
- `test/test_v2_phase2_entrypoint.py`

要做的事：

- 为 `codex` 增加：
  - `export_runtime_state()`
  - `resume()`
- 持久化最小可恢复字段：
  - `req_id`
  - `session_path`
  - `bound_turn_id`
  - `bound_task_id`
  - `next_seq`
  - `reader state` 中可序列化部分
  - `reply_buffer / last_* message cache`
- askd 重启后：
  - 重建 reader
  - 从已持久化 cursor 继续读
  - 同一 turn 若已进入 terminal pending，则直接 complete

验收标准：

- codex 长作业在 askd 重启后可继续完成
- 不重复输出已消费 completion items
- `watch / pend / get` 对同一 job 保持一致
- `turn_aborted` 与 `task_complete` 恢复后仍能正确映射状态

测试要求：

- `test_v2_execution_service.py`
  - codex submission persist + resume
  - codex terminal pending recovery
- `test_v2_phase2_entrypoint.py`
  - codex blackbox restart resume

当前状态：

- 已完成第一轮落地
- 已实现：
  - `codex` provider-level `export_runtime_state()`
  - `codex` provider-level `resume()`
  - codex execution unit tests
  - codex restart blackbox
- 当前结论：
  - `codex` 已从“只能 requires_resubmit”升级为“askd 重启后可继续完成”的真实 provider 样板

##### 15.7.8.2 第二步：补 Claude / Gemini 的 provider-level restore 策略

目标：

- 为 `claude / gemini` 建立各自独立的恢复方案，而不是强行复用 Codex 的逻辑
- 把 provider-specific completion detector 和 provider-specific restore 彻底绑定

原因：

- `claude` 更依赖 session event log / turn boundary
- `gemini` 更依赖 anchored snapshot / rotate / stability
- 三者完成信号和 cursor 模型不同，不能再继续混成一个统一“猜完成”逻辑

实现范围：

- `lib/provider_execution/claude.py`
- `lib/provider_execution/gemini.py`
- `lib/provider_execution/common.py`
- `test/test_v2_execution_service.py`
- `test/test_v2_phase2_entrypoint.py`

要做的事：

- `claude`：
  - 持久化 log reader state
  - 持久化 assistant / raw buffer / last assistant uuid
  - resume 后重新绑定 session path 并继续从 log 读
- `gemini`：
  - 持久化 snapshot cursor
  - 持久化 anchor 状态、reply buffer、session rotate 位置
  - resume 后重新 re-anchor
- 明确区分：
  - resume supported
  - resume degraded
  - resume unsupported

验收标准：

- `claude / gemini` 至少一条长作业黑盒能在 askd 重启后完成
- 若 provider 端状态确实不可恢复，也必须给出明确 degraded terminal，而不是挂死

测试要求：

- `test_v2_execution_service.py`
  - claude restore path
  - gemini restore path
- `test_v2_phase2_entrypoint.py`
  - claude/gemini restart blackbox

当前状态：

- 已完成第一轮 provider-level restore 落地
- 已实现：
  - `claude` provider-level `export_runtime_state()`
  - `claude` provider-level `resume()`
  - `gemini` provider-level `export_runtime_state()`
  - `gemini` provider-level `resume()`
  - 对应 execution unit tests
  - `claude` phase2 restart blackbox
  - `gemini` phase2 restart blackbox
- 当前结论：
  - `claude / gemini` 已和 `codex` 一样具备真实 askd restart resume 验证

##### 15.7.8.3 第三步：补“未落盘 completion batch”耐久层，继续收窄 crash window

目标：

- 解决当前边界里还存在的窗口：
  - provider 已产生 items
  - 但 askd 还没 append events.jsonl
  - 此时 crash 会丢中间 item

实现范围：

- `lib/provider_execution/state_models.py`
- `lib/provider_execution/service.py`
- `lib/askd/services/dispatcher.py`
- `lib/jobs/store.py`
- `test/test_v2_execution_service.py`
- `test/test_v2_askd_dispatcher.py`

要做的事：

- 在 execution state 中补：
  - `pending_items`
  - `pending_items_applied_at`
- `ExecutionService.poll()` 若返回 batch：
  - 先持久化 `pending_items`
  - dispatcher append 成功后再确认清空
- askd 重启时：
  - 若发现 pending items 未消费
  - 先重放 pending items
  - 再继续 provider poll

验收标准：

- crash 不再导致中间 completion items 静默丢失
- 重启后不会重复回放同一批 items
- event 顺序保持单调

测试要求：

- `test_v2_execution_service.py`
  - pending items persisted before apply
- `test_v2_askd_dispatcher.py`
  - replay pending items after restart

当前状态：

- 已完成第一轮落地
- 已实现：
  - execution state 中新增 `pending_items`
  - `ExecutionService.poll()` 先落盘 batch，再向 dispatcher 返回
  - `dispatcher` 对非 terminal batch 完成后显式 `acknowledge()`
  - `dispatcher` 在每个 completion item append 后执行前缀确认
  - restart 后可先 replay pending items，再继续 provider poll
- 当前边界：
  - 当前已从“整批 ack”推进到“按已落盘 item 前缀确认”
  - 若 crash 精确落在单个 event append 与 prefix confirm 之间，仍可能出现单 item 级重复
  - 这比之前“整批直接丢失 / 整批重复”已经更稳，但还不是最终形态

##### 15.7.8.4 第四步：统一 askd 为单守护模型并补守护自恢复策略

目标：

- 继续收敛守护模型，避免未来 provider 增多时 askd 外围逻辑再次膨胀
- 把 askd 稳定性从“能工作”提升为“可观测、可恢复、可自检”

实现范围：

- `lib/askd/app.py`
- `lib/askd/main.py`
- `lib/cli/services/daemon.py`
- `lib/cli/services/doctor.py`
- `test/test_v2_phase2_entrypoint.py`

要做的事：

- 补 askd 启动自检：
  - store schema
  - socket path
  - lease consistency
  - execution replay health
- 补守护恢复诊断：
  - last takeover cause
  - last restore summary
  - active execution count
  - recoverable / degraded / abandoned count
- 明确 `kill` 后的行为：
  - 当前项目 askd 全部退出
  - 下次 `ping/ask/pend/watch` 触发按规则重启

验收标准：

- `doctor` 能快速说明：
  - askd 是否稳定
  - 当前有多少 active executions
  - 哪些 provider 可恢复，哪些已降级
- 守护异常退出后，重启路径对用户是可解释的，而不是黑盒

测试要求：

- `test_v2_phase2_entrypoint.py`
  - askd restart self-check output
  - doctor restore summary

当前状态：

- 已完成第一轮落地
- 已新增 askd 诊断字段：
  - `active_execution_count`
  - `recoverable_execution_count`
  - `pending_items_count`
  - `terminal_pending_count`
- `doctor` 已同步输出：
  - `askd_active_execution_count`
  - `askd_recoverable_execution_count`
  - `askd_pending_items_count`
  - `askd_terminal_pending_count`

##### 15.7.8.5 第五步：建立第二阶段封板测试矩阵与发布准入

目标：

- 把“目前能跑”升级为“未来改动不容易回退”
- 为后续真正替换当前项目提供明确验收门槛

实现范围：

- `test/test_v2_phase2_entrypoint.py`
- `test/test_v2_execution_service.py`
- `test/test_v2_askd_dispatcher.py`
- `docs/agent-first-v2-architecture.md`

要做的事：

- 固化阶段性发布矩阵：
  - fake resume
  - codex resume
  - claude resume
  - gemini resume
  - unrecoverable fallback
  - terminal pending recovery
  - watch generation switch
  - doctor/ping diagnostics
- 增加封板准入规则：
  - 全量 pytest 通过
  - 关键 phase2 黑盒全绿
  - provider 恢复能力表与现实一致
  - 文档状态不能滞后于代码

验收标准：

- 第二阶段封板时能明确回答：
  - 哪些 provider 真支持 askd restart resume
  - 哪些仍只支持 requires_resubmit
  - crash window 还剩哪几类
- 覆盖结果能作为替换当前项目的直接验收材料

测试要求：

- 全量 `pytest -q`
- 单独保留 phase2 回归套件：
  - restart / resume
  - doctor / ping
  - watch / pend stability

当前状态：

- 已补强的矩阵覆盖包括：
  - fake restart resume
  - codex restart resume
  - claude restart resume
  - gemini restart resume
  - claude/gemini execution restore unit
  - terminal pending recovery
  - pending items replay
  - pending items prefix ack
  - doctor / ping execution diagnostics
- 本轮目标是以这些新增回归为基础执行全量 `pytest`

#### 15.7.9 基于当前新边界的后续 5 步执行计划

下面 5 步基于当前已经打通 `fake / codex / claude / gemini` 的 restart resume，
下一轮重点不再是“有没有恢复能力”，而是“恢复后的精度、可观测性与尾部 provider 收口”。

##### 15.7.9.1 第一步：把 `pending_items` 从前缀确认推进到单 event 级 exactly-once 语义

目标：

- 继续收窄 dispatcher append event 时的最后剩余 crash window
- 让 restart 后回放更接近单 event 级幂等，而不是当前的“最多重复 1 条”

要做的事：

- 为每个已写入 event 记录 apply marker
- 用 marker 而不是仅靠 in-memory loop 顺序判定是否该重放
- 把 replay 逻辑从“pending_items suffix”推进为“按 apply marker 精确跳过”

验收标准：

- crash 落在单 event append 后，也不应重复回放已落盘 item
- event_seq 与 event store 顺序仍保持单调

##### 15.7.9.2 第二步：为 `claude / gemini` 增加更强的长静默与 rotate soak 黑盒

目标：

- 把当前 restart 黑盒从“基本恢复”升级到“复杂场景稳定恢复”

要做的事：

- `claude`
  - 长静默后 turn_duration 恢复
  - rotate / subagent 相关边界
- `gemini`
  - silent-gap
  - session rotate 后恢复
  - anchored snapshot 稳定窗口 soak

验收标准：

- 复杂场景下 `pend/watch/get` 仍然一致
- 不因长静默误判 terminal 或丢失稳定 reply

##### 15.7.9.3 第三步：补 `opencode / droid` 的 execution persistence 与明确降级策略

目标：

- 让尾部 provider 不再停留在“模糊 unsupported”
- 要么接入恢复，要么给出明确、可观测、可测试的降级路径

要做的事：

- 先评估 `opencode / droid` 的 runtime state 可序列化面
- 若短期不能 resume：
  - 明确 `resume_capable = false`
  - 明确 `doctor/ping` 中的降级说明
- 若可行：
  - 先接 unit 级 restore

验收标准：

- 用户能明确知道这两类 provider 的恢复能力边界
- 不会出现“看起来应该恢复、实际上 silently fallback”的灰区

当前状态：

- 已完成“明确降级”这一半：
  - `opencode / droid` adapter 显式声明 restart 后需要 resubmit
  - execution state 会持久化 `resume_supported / restore_mode / restore_reason / restore_detail`
  - `doctor/ping` 会直接暴露这些字段
- 尚未完成 provider-level resume：
  - 目前仍不尝试跨 askd 重启恢复 `opencode / droid` 的 live reader/backend
  - 若运行中遇到 askd 重启，这两类 provider 仍按 `askd_restart_requires_resubmit` 收口
- 这意味着当前边界已经清晰，但能力仍属于“明确降级”而不是“可恢复”

##### 15.7.9.4 第四步：把 askd 自检做成显式启动报告与恢复摘要

目标：

- 让 askd 的自恢复不再像黑盒
- 启动后能快速告诉用户“接管了什么、恢复了什么、放弃了什么”

要做的事：

- askd 启动时汇总：
  - recovered executions
  - replayed pending items
  - terminal-pending completions
  - abandoned executions
- `doctor/ping` 提供最近一次恢复摘要

验收标准：

- 守护异常退出后，用户能从输出直接判断恢复结果
- 不需要翻 job/event jsonl 才知道发生了什么

当前状态：

- 已落地 `restore-report.json`
  - 路径：`.ccb/askd/restore-report.json`
  - 记录最近一次 askd 启动扫描到的 running jobs 恢复摘要
- 已接入以下汇总字段：
  - `last_restore_running_job_count`
  - `last_restore_restored_execution_count`
  - `last_restore_replay_pending_count`
  - `last_restore_terminal_pending_count`
  - `last_restore_abandoned_execution_count`
  - `last_restore_already_active_count`
  - `last_restore_results_text`
- `ping askd` 与 `doctor` 已可直接展示最近一次恢复摘要
- 这使 askd 启动恢复从“黑盒”变成了“最近一次恢复结果可读、可测、可回归”

##### 15.7.9.5 第五步：形成替换当前项目的最终封板清单

目标：

- 为后续覆盖当前项目提供直接可执行的验收门槛

要做的事：

- 固化 provider 能力表：
  - fake
  - codex
  - claude
  - gemini
  - opencode
  - droid
- 固化 phase2 回归套件最小集合
- 固化“可以覆盖旧项目”的通过条件

验收标准：

- 文档中能明确列出：
  - 哪些 provider 已可 restart resume
  - 哪些只支持明确降级
  - 剩余风险是什么

当前能力表：

- 已支持 restart resume：
  - `fake`
  - `codex`
  - `claude`
  - `gemini`
- 已支持显式降级但不支持 restart resume：
  - `opencode`
  - `droid`
- askd 侧已支持：
  - running execution state 持久化
  - pending items durable replay
  - terminal pending recovery
  - 最近一次启动恢复摘要输出
- 剩余主要风险：
  - `pending_items` 仍是 event 级确认，但还没有独立 apply marker
  - `claude / gemini` 还缺更长静默与 rotate soak
  - `opencode / droid` 还没有 provider-native resume

#### 15.7.10 面向替换落地前的下一轮未来 5 步执行计划

当前位置：

- v2 的核心闭环已经成立：
  - askd 单守护
  - agent-first 命名与调度
  - running execution state 持久化
  - `fake / codex / claude / gemini` restart resume
  - `opencode / droid` 明确降级
  - `doctor / ping` 恢复诊断可见
- 当前主要风险已从“功能是否打通”切换为两类：
  - 框架级幂等与恢复不变量还可继续收紧
  - 通讯层与 provider reader 层复杂度偏高，后续扩展新 provider 成本仍然偏大
- 基于当前热点分析，复杂度风险主要集中在：
  - `lib/opencode_comm.py`
  - `lib/claude_comm.py`
  - `lib/terminal.py`
  - `lib/codex_comm.py`
  - `lib/gemini_comm.py`
  - `lib/droid_comm.py`

最新 `archi` 基线补充（2026-03-21）：

- 已再次执行 `archi .`
- 当前版本稳定产出的产物为：
  - `.architec/architec-hotspots-topk.json`
  - `.architec/architec-history-report.json`
  - `.architec/architec-debt-ledger.json`
- 当前版本未稳定自动生成：
  - `.architec/architec-summary.md`
  - `.architec/architec-analysis.json`
- 历史问题总量：
  - total = `802`
  - critical = `252`
  - warning = `445`
  - info = `105`
- 问题维度分布：
  - complexity = `391`
  - code_style = `284`
  - file_size = `103`
  - encapsulation = `24`
- 热点 Top 8：
  - `lib/opencode_comm.py`
  - `lib/claude_comm.py`
  - `lib/terminal.py`
  - `lib/codex_comm.py`
  - `lib/laskd_registry.py`
  - `lib/gemini_comm.py`
  - `lib/droid_comm.py`
  - `lib/askd/adapters/claude.py`
- 直接含义：
  - 当前最该优先处理的不是再加新能力，而是压低通讯层和 provider 适配层的圈复杂度
  - 第一步与第二步的顺序不能交换，否则 provider 功能继续叠加会放大热点文件
  - `opencode / claude / terminal / codex` 应作为通讯层拆分的第一批对象

这一轮不建议再先扩功能面，而应先把“框架不变量 + 热点拆分 + provider 收口”一起做完。

##### 15.7.10.1 第一步：把 `pending_items` 推进到 apply-marker 驱动的精确回放

目标：

- 把 restart replay 从“接近 exactly-once”推进到“有独立落盘依据的精确跳过”
- 进一步缩小 event append 后的 crash window

要做的事：

- 为每个 completion item 引入独立 apply marker
- dispatcher 处理完成后，按 marker 而不是仅靠 `event_seq` 前缀裁剪
- 明确 replay 判定顺序：
  - 先看 marker
  - 再看 pending item
  - 再看 terminal pending
- 为以下边界补测试：
  - append 成功但 ack 前崩溃
  - 多 item 批次中间崩溃
  - terminal item 已写 event 但 terminal decision 未完成

验收标准：

- restart 后不会重复 append 已持久化 completion event
- `watch / get / pend` 在 crash-replay 后仍保持一致
- replay 行为能通过黑盒测试稳定复现

当前状态：

- 已完成第一轮 apply-marker 落地：
  - execution state 新增 `applied_event_seqs`
  - dispatcher append `completion_item` 后，会立刻按 item 的 `event_seq` 记录 apply marker
  - restore 时会先过滤已标记 item，再决定：
    - replay remaining pending items
    - 或直接进入 `terminal_pending`
- 已修正一处恢复链路问题：
  - provider resume 成功后，不再把尚未 replay 的 `pending_items` 从持久态里提前抹掉
  - 这样 askd 在“刚恢复成功但尚未完成 replay”期间再次崩溃，也不会丢失待回放 item
- 当前语义是：
  - `acknowledge_item()` 负责单 item apply marker
  - `acknowledge()` 仍保留批量确认语义，用于本轮 replay 完成后统一清空 `pending_items`
- 已补测试覆盖：
  - exact item marker 不再按前缀裁剪
  - apply marker 参与 restart replay 过滤
  - terminal pending 能基于 apply marker 直接恢复

##### 15.7.10.2 第二步：把 provider 通讯热点拆成稳定子模块，消除巨石文件

目标：

- 降低 `*_comm.py` 与 terminal 交互层的圈复杂度
- 为新增 provider 和 completion detector 预留清晰插槽

要做的事：

- 按职责把热点文件拆为最小稳定层：
  - session discovery
  - log reader
  - event parser
  - completion extraction
  - resume state helper
- 优先拆以下高风险文件：
  - `lib/opencode_comm.py`
  - `lib/claude_comm.py`
  - `lib/codex_comm.py`
  - `lib/gemini_comm.py`
  - `lib/droid_comm.py`
  - `lib/terminal.py`
- 保持 dispatcher / execution service 不感知 provider 私有细节
- 为每个 provider 增加最小 adapter contract test

验收标准：

- 不再继续放大通讯层巨石文件
- provider-specific 复杂逻辑被收敛到 provider 自己目录下
- 新增 provider 时不需要复制粘贴现有大文件逻辑

当前状态：

- 已完成第一轮 `opencode` 外围职责拆分：
  - 新增 `lib/opencode_runtime/paths.py`
    - 负责 project-id 计算、路径归一化、workdir 匹配、storage/log root 推导
  - 新增 `lib/opencode_runtime/watch.py`
    - 负责 session watcher 与 `.opencode-session` 绑定更新
  - 新增 `lib/opencode_runtime/logs.py`
    - 负责 cancel log 文件选择与时间解析
- `lib/opencode_comm.py` 当前已从 `1680+` 行收缩到约 `1320` 行
- 这一步没有改 `OpenCodeLogReader` / `OpenCodeCommunicator` 的公开接口，目的就是先把全局辅助职责剥离出去
- 已完成的验证：
  - `test_opencode_comm_sqlite.py`
  - `test_session_file_override.py -k opencode`
  - `test_v2_execution_service.py -k opencode`
- 下一步拆分重点应继续推进到：
  - `OpenCodeLogReader` 内部的 DB/file storage access
  - event parsing / reply extraction
  - communicator 与 reader 的耦合边界

进一步进展：

- 已完成第二轮 `OpenCodeLogReader` storage access 抽离：
  - 新增 `lib/opencode_runtime/storage.py`
  - 抽出：
    - session/message/part directory routing
    - JSON blob / file load
    - SQLite candidate resolve / row fetch
    - message / part sort key
- `lib/opencode_comm.py` 已进一步从约 `1320` 行收缩到约 `1226` 行
- 当前 `OpenCodeLogReader` 已不再直接持有 DB path resolve / row fetch 细节
- 已补验证：
  - `test_opencode_comm_sqlite.py`
  - `test_session_file_override.py -k opencode`
  - `test_v2_execution_service.py -k opencode`
  - `test_v2_askd_socket.py -k opencode`
- 下一步应继续处理的仍是：
  - session discovery
  - event parsing / reply extraction
  - communicator / reader 生命周期边界

进一步进展：

- 已完成第三轮 `event parsing / reply extraction` 抽离：
  - 新增 `lib/opencode_runtime/replies.py`
  - 抽出：
    - `extract_text`
    - latest message 选择
    - conversation pair 提取
    - 增量 assistant reply 判定
    - aborted error / req id 提取
- `lib/opencode_comm.py` 已进一步从约 `1226` 行收缩到约 `1108` 行
- 当前 `OpenCodeLogReader` 已逐步退回到：
  - session selection
  - state orchestration
  - 对 storage / reply helper 的调度
- 已补验证：
  - `test_opencode_comm_sqlite.py`
  - `test_session_file_override.py -k opencode`
  - `test_v2_execution_service.py -k opencode`
  - `test_v2_askd_socket.py -k opencode`
- 到这一轮为止，`opencode` 的下一优先拆分点已经收敛为：
  - session discovery
  - communicator / reader 生命周期边界
  - 然后转向 `lib/terminal.py`

进一步进展：

- 已开始处理 `lib/terminal.py` 这个公共热点
- 当前已完成七轮“纯工具层 / 探测层 / layout 层 / WezTerm spawn 层 / tmux respawn 层 / WezTerm input 层 / tmux attach-input 层”拆分：
  - 新增 `lib/terminal_runtime/env.py`
    - 环境变量解析
    - WSL / Windows / WezTerm 路径探测
    - 默认 shell 选择
  - 新增 `lib/terminal_runtime/pane_logs.py`
    - pane log root / path / trim / cleanup
  - 新增 `lib/terminal_runtime/detect.py`
    - 当前 TTY 探测
    - tmux / WezTerm 运行环境判定
    - `detect_terminal` 统一判定入口
  - 新增 `lib/terminal_runtime/wezterm.py`
    - `wezterm cli list` JSON / 文本回退解析
    - pane title marker 匹配
    - `wezterm cli` 存活探测
  - 新增 `lib/terminal_runtime/tmux.py`
    - tmux socket base command 组装
    - pane / target 判定
    - split direction 规范化
    - `list-panes` marker 匹配解析
    - detached session name 生成
  - 新增 `lib/terminal_runtime/layouts.py`
    - tmux root pane 解析与 detached session 复用
    - 1/2/3/4 pane 拓扑编排
    - marker 标题分配
    - `needs_attach / created_panes` 结果统一
  - 新增 `lib/terminal_runtime/wezterm_spawn.py`
    - WezTerm `split-pane` 参数组装
    - 是否走 WSL launch 的判定
    - Windows 路径到 WSL cwd 的解析
    - WSL 下 WezTerm CLI run cwd 选择
  - 新增 `lib/terminal_runtime/tmux_respawn.py`
    - tmux start dir 规范化
    - stderr log redirection 组装
    - shell / shell flags 选择
    - shell command quoting
    - `respawn-pane` argv 组装
  - 新增 `lib/terminal_runtime/wezterm_input.py`
    - special key variants 选择
    - enter method 标准化
    - 文本清洗与发送模式分类
    - enter retry 基线参数
  - 新增 `lib/terminal_runtime/tmux_attach.py`
    - user option 标准化
    - pane exists / pipe enabled / alive 判定
    - attach session name 解析
    - select 后是否需要 attach 的判定
  - 新增 `lib/terminal_runtime/tmux_input.py`
    - tmux 文本清洗
    - legacy inline send 判定
    - buffer name 生成
    - copy mode 标志判定
- `lib/terminal.py` 已从约 `1518` 行进一步收缩到约 `1048` 行
- 保留了原有函数名与调用入口，目的是不破坏现有 monkeypatch 测试与 provider 调用方
- 已补验证：
  - `test_terminal_runtime_layouts.py`
  - `test_terminal_runtime_tmux_attach.py`
  - `test_terminal_runtime_tmux_input.py`
  - `test_terminal_runtime_tmux.py`
  - `test_terminal_runtime_tmux_respawn.py`
  - `test_terminal_runtime_wezterm.py`
  - `test_terminal_runtime_wezterm_input.py`
  - `test_terminal_runtime_wezterm_spawn.py`
  - `test_wsl_path_utils.py`
  - `test_detect_terminal.py`
  - `test_tmux_backend.py`
  - `test_tmux_respawn_pane.py`
  - `test_session_ensure_pane.py`
  - `test_caskd_session_ensure_pane.py`
  - `test_gaskd_session_ensure_pane.py`
  - `test_baskd_session_ensure_pane.py`
  - `test_v2_execution_service.py -k 'codex or claude or gemini or opencode or droid'`
  - `test_v2_askd_socket.py -k 'codex or claude or gemini or opencode'`
  - `pytest -q`
    - 当前结果：`476 passed`
- 下一步应继续在 `terminal.py` 中拆：
  - tmux pane log / attach / activate 编排细节
  - 然后转向 `15.7.10.3` 的 completion 收口阶段

##### 15.7.10.3 第三步：完成 `claude / gemini / opencode / droid` 的 completion 收口

目标：

- 主 provider 继续增强稳定终态识别
- 次 provider 把 observed/degraded 路径做可信，而不是只停留在 smoke

要做的事：

- `claude`
  - 补长静默与 session rotate soak
  - 明确 subagent / child turn 边界是否影响 terminal 判定
- `gemini`
  - 补 silent-gap / snapshot-stability soak
  - 明确 rotate 后 anchored snapshot 的恢复语义
- `opencode / droid`
  - 增强 observed completion item 映射
  - 统一 cancel / pane-dead / session-rotate 行为
  - 明确 reply merge 与 final answer 提取边界

当前已完成的第一轮收口：

- 已为 `claude / opencode / droid` 补齐 `session rotate -> re-anchor` 行为
  - 旧 session 的 anchor/reply 缓冲在 rotate 后不再污染新 session
  - 新 session 的第一批 provider 输出会重新建立 `ANCHOR_SEEN`
- 已为 `claude` 补齐 `subagent / child turn` 边界保护
  - 子代理 assistant 事件不会再覆盖主 turn 的 `last_assistant_uuid`
  - 子代理 `turn_duration` 不会错误触发主 turn `TURN_BOUNDARY`
- 已为 `gemini` 补齐 detector 级保护：
  - `SESSION_ROTATE` 后若没有新的 snapshot/reply，settle window 到期也不得完成
- 已为 `gemini` 补齐 selector/tracker/askd 级保护：
  - `SESSION_ROTATE` 后旧 `SESSION_REPLY` preview 会被清空
  - 不会再在 `running` 状态下残留旧 session 的 reply 预览
- 已为 `gemini` 补齐 phase2 黑盒保护：
  - `pend` 在 rotate 后的 `running` 状态下也不会显示旧 reply
  - 这意味着 `detector + selector + tracker + askd socket + phase2 CLI` 已形成一致语义
- 已补黑盒覆盖：
  - `test_execution_service_claude_adapter_reanchors_after_session_rotate`
  - `test_execution_service_claude_adapter_ignores_subagent_turn_boundary`
  - `test_execution_service_claude_adapter_after_rotate_only_new_main_boundary_completes`
  - `test_ccb_claude_real_adapter_blackbox_rotate_and_subagent_only_new_main_boundary_completes`
  - `test_ccb_claude_real_adapter_recovers_after_askd_restart_rotate_and_subagent_only_new_main_boundary_completes`
  - `test_execution_service_opencode_adapter_reanchors_after_session_rotate`
  - `test_execution_service_droid_adapter_reanchors_after_session_rotate`
  - `test_askd_socket_gemini_rotate_clears_stale_reply_preview`
  - `test_ccb_gemini_real_adapter_blackbox_clears_stale_reply_preview_after_rotate`
  - `test_ccb_gemini_real_adapter_recovers_after_askd_restart_and_rotate_clears_stale_preview`
  - `test_ccb_gemini_real_adapter_blackbox_waits_for_last_snapshot_mutation_to_settle`
  - `test_ccb_gemini_real_adapter_recovers_after_askd_restart_and_waits_for_post_restart_mutation_settle`
  - `test_ccb_gemini_real_adapter_recovers_after_restart_rotate_and_waits_for_new_session_mutation_settle`
- 已补 legacy/degraded 回归：
  - `test_legacy_text_quiet_detector_fails_on_pane_dead`
  - `test_askd_socket_opencode_pane_dead_becomes_failed_degraded`
  - `test_askd_socket_droid_pane_dead_becomes_failed_degraded`
  - `test_ccb_opencode_real_adapter_blackbox_pane_dead_fails_degraded`
  - `test_ccb_droid_real_adapter_blackbox_pane_dead_fails_degraded`
  - `test_ccb_opencode_real_adapter_blackbox_legacy_done_marker_completion`
  - `test_ccb_droid_real_adapter_blackbox_legacy_done_marker_completion`
  - `test_ccb_opencode_real_adapter_blackbox_cancel_stops_legacy_completion`
  - `test_ccb_droid_real_adapter_blackbox_cancel_stops_legacy_completion`
- 已补 completion/provider 回归：
  - `test_v2_completion_detectors.py`
  - `test_v2_completion_orchestration.py`
  - `test_v2_completion_tracker.py`
- 这一轮完成后：
  - `session rotate` 的 completion 语义已经从“部分 provider 有定义”推进到“主 provider 与 legacy provider 都有明确重锚点行为”
  - `claude` 的主 turn / child turn 边界也已经从“依赖日志偶然性”推进到“有明确黑盒保护”
  - `claude` 的 phase2 命令面也已验证：`rotate + subagent mixed events` 下，旧 session 与 child boundary 都不会误完成，只有新主 assistant boundary 会收口
  - `claude` 的 askd restart 恢复链路也已验证：重启前的旧 session preview 不会越过 rotate 延续到最终完成态，恢复后仍只接受新主 assistant boundary
  - `gemini` 的 `detector + selector + tracker + askd socket + phase2 CLI` 在 rotate 后也已具备一致的“旧 reply 清空”语义
  - `gemini` 的 `askd restart + session rotate` 组合场景也已补齐 phase2 黑盒，确认重启恢复后不会继续泄漏旧 preview，且仅在新 session reply 稳定后收口
  - `gemini` 的 phase2 命令面也已验证：同一条 snapshot 多次 mutation 时，不会在最后一次变更刚出现时提前完成，必须等待最终 settle window
  - `gemini` 的 askd restart 恢复链路也已验证：重启后若同一条 snapshot 继续 mutation，仍会以“最后一次 mutation 后重新计时”的语义收口，不会复用重启前 preview 的稳定窗口
  - `gemini` 的 `restart + rotate + mutation` 三者叠加组合场景也已补齐 phase2 黑盒：恢复后先清空旧 session preview，再以新 session 的最后一次 mutation 重新计时收口
  - `legacy_text_quiet` 家族已补齐 `pane_dead -> failed/degraded` 终态映射，`opencode / droid` 在 pane 死亡时不再可能挂在 pending
  - `opencode / droid` 的 phase2 命令面也已验证：`ask -> pend -> watch` 会把 `pane_dead` 明确暴露为 `failed + degraded`
  - `opencode / droid` 的 phase2 正常 legacy 路径也已验证：`legacy_done_marker` 会稳定收口为 `completed + degraded`
  - `opencode / droid` 的 phase2 cancel 路径也已验证：`cancel` 会把 job 锁定为 `cancelled + degraded`，后续 legacy final 不会覆盖终态

下一步建议的 completion 收口顺序：

1. `gemini`
   - 增加更长时间窗口的 silent-gap / snapshot-stability soak
   - 增加跨更长静默窗口的 restart + rotate + mutation soak
2. `claude`
   - 增加更长日志序列下的多轮 child/main 交错 soak
   - 增加跨多次 rotate 的 child/main 交错 soak
3. `opencode / droid`
   - 增加 `no-done-marker` 的降级语义测试
   - 统一 `ASSISTANT_CHUNK / ASSISTANT_FINAL` 与 selector 提取边界

验收标准：

- `claude / gemini` 黑盒在长时运行下不误判完成
- `opencode / droid` 至少达到“可观测、可解释、可测试”的稳定降级
- completion family 与实际输出行为一致，不出现名义与实现脱节

##### 15.7.10.4 第四步：建立 askd 状态修复与运维面板能力

目标：

- 让 v2 不只是“能恢复”，还要“可诊断、可修复、可维护”

要做的事：

- 在 `doctor` 基础上补项目级状态审计项：
  - runtime binding 异常
  - orphan execution state
  - snapshot / cursor / execution state 不一致
  - restore report 与当前状态不一致
- 规划最小修复命令集合：
  - 只读 audit
  - 安全清理 orphan state
  - 重建 askd 派生状态
- 为 askd 单守护模型补寿命测试：
  - kill/restart 循环
  - stale socket takeover
  - heartbeat 断续恢复

验收标准：

- 用户无需手工翻 `.ccb/askd/*` 就能定位常见故障
- askd 状态损坏时有明确的诊断路径和修复路径
- 守护代际切换不再依赖人工经验排障

##### 15.7.10.5 第五步：做覆盖旧项目前的替换演练与发布门禁

目标：

- 在真正覆盖当前项目之前，完成一次完整的替换演练
- 把“能不能替换”从主观判断变成明确门禁

要做的事：

- 固化替换前发布门禁：
  - 全量 `pytest -q`
  - phase2 核心黑盒矩阵
  - provider capability matrix
  - askd restart / kill / takeover / replay 回归
- 做一次迁移演练：
  - 从干净项目初始化
  - 启动多个 agent
  - ask / watch / pend / ping / doctor / kill 全流程
  - 模拟守护重启与 provider 恢复
- 形成最终替换 checklist：
  - 哪些功能已达标
  - 哪些 provider 仍属明确降级
  - 哪些命令语义与旧项目不同

验收标准：

- 文档中能明确给出“可替换 / 暂不可替换”的判定
- 替换风险、剩余降级项、测试门槛全部可读
- 覆盖当前项目时不再需要边改边猜

顺序理由：

1. 先做 apply marker，是因为它决定恢复语义是否真正收口
2. 再拆通讯热点，是因为继续叠加 provider 逻辑会迅速放大维护成本
3. 然后做 completion 收口，才能让 provider 行为和测试矩阵一起稳定
4. 再补 askd 运维与修复面，保证系统出问题时可控
5. 最后做替换演练，把前面所有能力转成真正的发布门禁

##### 15.7.10.6 面向旧框架功能回归的未来 5 步执行计划（不含邮件）

本轮之后，下一阶段不应再只围绕“新架构本身是否自洽”推进，而要开始系统回答：

- 旧框架中，除邮件链路外，用户真正依赖的能力是否都已被 v2 覆盖
- 哪些只是“代码层旧实现”，哪些是“用户层必须回归的功能”
- 在不保留旧命令别名和旧内部结构的前提下，v2 是否已经具备替换旧项目的功能面

这一轮的规划边界明确如下：

- 纳入回归范围：
  - `ccb` 启动/附着
  - `-r` 恢复
  - `-a` 权限模式透传
  - `ask / pend / watch / cancel / kill / ping / ps / doctor`
  - 项目解析、默认配置、workspace/worktree、session/runtime binding
  - tmux / WezTerm 运行时
  - `claude / codex / gemini / opencode / droid / fake` 非邮件链路
- 明确排除：
  - `maild`
  - 所有邮件配置、收发、轮询、IMAP/SMTP 相关能力
  - 旧 provider 独立脚本命令名本身的兼容性
    - 例如 `cask/gask/oping/...`
    - 这里回归的是“功能能力”，不是“旧命令别名”

下面 5 步应作为“覆盖旧项目能力面”的主执行顺序。

###### 15.7.10.6.1 第一步：把旧框架非邮件功能面固化为回归矩阵

目标：

- 不再凭感觉说“差不多能替换”
- 先把旧框架真正需要回归的用户面列成固定清单

要做的事：

- 基于旧 README、当前 README、现有 phase2 测试能力，整理非邮件回归矩阵：
  - 启动类
    - `ccb`
    - `ccb <agent>`
    - `ccb -r`
    - `ccb -a`
    - `ccb -a -r`
  - 交互类
    - `ccb ask`
    - `ccb pend`
    - `ccb watch`
    - `ccb cancel`
  - 诊断/运维类
    - `ccb ping`
    - `ccb ps`
    - `ccb doctor`
    - `ccb kill`
  - 生命周期类
    - askd restart
    - provider restore
    - stale socket takeover
    - runtime/session/workspace binding 一致性
  - 终端类
    - tmux 启动
    - WezTerm 启动
    - pane/workspace 绑定
    - session 文件追踪
- 为每一项标记：
  - 已覆盖
  - 部分覆盖
  - 未覆盖
  - 是否已有 unit/socket/phase2 黑盒
- 单独列出“旧项目有、v2 暂不回归”的项：
  - 仅保留邮件相关
  - 不夹带其它模糊例外

验收标准：

- 文档中出现一张明确的“旧框架非邮件功能回归矩阵”
- 每个能力点都有当前状态
- 不再把“命令别名兼容”与“用户功能回归”混为一谈

###### 15.7.10.6.2 第二步：补齐核心命令面的 phase2 回归黑盒

目标：

- 让旧框架核心命令在 v2 上形成可替换的命令面闭环

要做的事：

- 围绕以下命令补 phase2 黑盒：
  - `ccb`
  - `ccb -r`
  - `ccb -a`
  - `ccb -a -r`
  - `ccb ask`
  - `ccb pend`
  - `ccb watch`
  - `ccb cancel`
  - `ccb ping`
  - `ccb ps`
  - `ccb doctor`
  - `ccb kill`
- 不再只测单 provider happy path，而要覆盖：
  - default agent 启动
  - 指定 agent 启动
  - 多 agent 启动
  - 运行中 kill
  - kill 后重新拉起
  - 未挂载状态下的 ping/ps/doctor
- 所有回归优先使用 `phase2_entrypoint`，因为这最接近替换时真实用户路径

验收标准：

- 旧框架的核心非邮件命令全部至少有一条 phase2 黑盒
- `ask -> pend/watch -> cancel/kill` 的命令面不再存在无测试空洞
- `ps / doctor / ping` 对 binding/runtime/session/workspace 的输出可作为稳定契约

###### 15.7.10.6.3 第三步：补齐恢复与项目解析回归

目标：

- 把旧框架里最容易“看起来能用，实际一重启就坏”的路径收口

要做的事：

- 增强以下回归：
  - `-r` 对已有 restore state 的读取与覆盖行为
  - askd restart 后的恢复报告
  - provider resume / resubmit_required / abandoned 三种路径
  - `.ccb` 锚点项目解析
  - workspace 内执行命令时回溯到 target project
  - stale session path / stale runtime ref 的修正行为
- 为旧框架曾经高频出问题的场景补黑盒：
  - 错项目目录执行
  - runtime 已挂但 session 过期
  - askd lease/socket 脏状态
  - kill 后重新 `ccb -r`

验收标准：

- `-r` 不只是“字段存在”，而是有明确行为契约
- 项目解析错误时稳定失败，不会误投递到错误项目
- askd restart/kill/takeover/rebind 形成可复现的回归套件

###### 15.7.10.6.4 第四步：补齐终端与工作区回归

目标：

- 让旧框架用户最直观依赖的 tmux/WezTerm/worktree 体验有明确回归保护

要做的事：

- 以旧项目实际体验为参照，回归以下能力：
  - tmux / WezTerm pane 启动
  - pane attach / respawn / input
  - session 文件定位与追踪
  - workspace/worktree 路径正确性
  - `ps / doctor` 对 workspace/binding 的可观测输出
- 补多 agent 场景：
  - 同项目多个 agent
  - 同 provider 多 agent
  - kill 后 workspace 不混乱
  - restore 后 runtime ref / session ref / workspace path 仍一致
- 保持边界：
  - 回归“功能体验”
  - 不回归旧 tmux 配色、旧脚本命令名、旧零散实现细节

验收标准：

- 终端层回归不再只停留在 unit test
- 多 agent + 独立 workspace 的旧用户心智在 v2 中可验证
- tmux/WezTerm 相关回归失败时可以准确定位到 terminal_runtime 或 binding 生命周期

###### 15.7.10.6.5 第五步：形成旧框架替换门禁（不含邮件）

目标：

- 明确回答：在不考虑邮件系统的前提下，v2 是否已经可以覆盖旧框架主用法

要做的事：

- 基于前 4 步形成替换门禁：
  - 非邮件功能回归矩阵通过率
  - phase2 核心命令黑盒通过
  - 恢复/重启/takeover 回归通过
  - tmux/WezTerm/workspace 回归通过
  - provider capability matrix 更新
- 单独输出“未替换项”：
  - 邮件系统
  - 明确暂不回归的命令别名
  - 明确仍属 degraded 的 provider 能力
- 给出替换结论：
  - 可替换：旧框架非邮件主路径
  - 暂不可替换：邮件链路与被明确排除项

验收标准：

- 能给出“旧框架非邮件能力是否可替换”的书面判定
- 剩余缺口只剩邮件与文档中显式列出的排除项
- 替换决策不再依赖人工经验判断

#### 15.7.6 第二阶段第六步：增强 OpenCode / Droid 的 observed completion

当前 `opencode / droid` 的状态是正确的，但只到“已进入 v2 架构”。

目标：

- 不追求一步到 exact
- 先把 observed / degraded 路径做得更可信
- 再评估是否存在 provider-native 更强终态信号

实现范围：

- `lib/provider_execution/opencode.py`
- `lib/provider_execution/droid.py`
- `lib/opencode_comm.py`
- `lib/droid_comm.py`

优先补的能力：

- cancel / pane-dead / session-rotate 一致性
- reply 质量提升
- provider 私有日志与 v2 completion item 的映射细化

明确不建议现在做的事：

- 不要为了追 exact 而把 provider 私有状态机重新塞回 dispatcher
- 不要因为这两家目前是 degraded，就把 `legacy_text_quiet` 永久化成默认终态模型

#### 15.7.7 第二阶段总验收标准

进入第二阶段封板前，至少应满足：

- `claude` 不再默认依赖 `CCB_DONE`
- `codex` 完成信号收敛到结构化 turn 终态
- `gemini` 补齐 long-running / silent-gap 稳定性测试
- askd 完成 generation / reconnect / heartbeat 稳定性验证
- `opencode / droid` 的 v2 adapter 不再只是 smoke 级别

建议第二阶段的主测试命令：

```bash
pytest -q
pytest -q test/test_v2_execution_service.py test/test_v2_askd_socket.py test/test_v2_phase2_entrypoint.py test/test_v2_askd_dispatcher.py
```

阶段推进顺序必须固定为：

1. `claude` completion 升级
2. `codex` exact completion 升级
3. `gemini` soak / silent-gap 封板
4. runtime binding 生命周期收敛
5. askd 守护稳定性与代际测试
6. `opencode / droid` observed completion 增强

原因很简单：

- 先处理主 provider 的完成判定
- 再处理框架不变量
- 最后再增强次路径 provider

这样才能避免在主路径还不稳时，把精力分散到低优先级 provider 上。

## 16. 关键结论

v2 的关键不是“允许多个同类 provider 进程同时跑”，而是：

- 用 `agent_name` 替代 `provider` 成为主身份
- 用统一 `askd` 取代多守护分裂
- 用 agent 控制目录 + 独立真实工作区解决并发冲突
- 用 agent 级恢复状态重定义 `-r`
- 用统一权限策略重定义 `-a`

最终用户心智模型应当非常简单：

- 我启动的是 agent，不是 provider
- 我恢复的是 agent，不是某个散落的 provider session
- 我给 agent 发消息，底层 provider 只是实现细节
- 我可以在同一个项目里并发运行多个同类 agent，因为它们的状态和工作区都是隔离的

## 17. Clean-Cut Refactor Directive

本节作为后续代码修改的硬约束。

目标不是“把旧框架包装进 v2”，而是：

- 让 `ccb_source` 成为单一、干净、可扩展的新框架
- 明确舍弃旧架构中的历史兼容层、降级兜底和双轨实现
- 若某些行为需要参考旧框架，只允许“参考实现思路”，不允许把旧运行时语义继续搬进新框架

### 17.1 当前架构位置

当前 `ccb_source` 已有清晰的 v2 主骨架：

- `agents/`
- `project/`
- `workspace/`
- `askd/`
- `provider_execution/`
- `completion/`
- `storage/`
- `cli/`

但同时仍残留明显的旧框架污染：

- `CompatibilityMode` 与一整套 compatibility / fallback 设计仍在核心模型中
- `session_utils.py` 仍继续向 `.ccb_config/` 和项目根目录做 legacy session 搜索
- `terminal.py` 仍保留大量“pane_id 或 session name 二义性”的旧行为
- `askd/adapters/*` 仍承载旧同步 daemon 语义，与 `provider_execution/*` 形成双轨
- 顶层 `ccb` 入口仍同时承载 phase1 / phase2 与大量旧启动逻辑
- 文档中仍默认接受“先保留 legacy，再慢慢收缩”的过渡路线

这与“新框架干净、整洁、不做兜底”的目标冲突。

### 17.2 硬原则

后续重构必须满足以下原则：

- 只保留一个新框架主路径，不维护新旧双轨运行时
- 不为了旧数据、旧目录、旧命令、旧 daemon 继续污染核心模型
- compatibility/fallback 不是默认能力；能删就删，不在运行时保留
- 旧框架仅作为参考样本，不作为新框架的隐式行为规范
- 优先保证模型层、状态层、路径层、守护层的边界纯净
- 如果某个 provider 目前做不到稳定，就明确降级为“暂不支持”，而不是加一层兜底

### 17.3 明确要删除的历史能力

以下能力不应继续留在新框架核心运行时：

- `.ccb_config/` 目录兼容
- 项目根目录直接放 `.codex-session` / `.claude-session` 之类的 legacy 查找
- `CompatibilityMode.STRICT / ALLOW_FALLBACK / LEGACY_PRIMARY` 这套全局策略
- `legacy_text_quiet` 作为通用过渡模型长期存在
- 旧的 `caskd / gaskd / oaskd / daskd / laskd` 思维继续渗透 askd 设计
- `terminal.py` 中“pane target / tmux session name 混用”的兼容接口
- 以 provider 私有 prompt marker 为主的完成协议
- phase1 / phase2 长期并存
- 旧命令别名与旧目录结构的透明兼容

结论：

- 这些能力如果影响用户迁移，应通过迁移脚本、一次性升级命令或文档说明解决
- 不应继续留在长期运行时代码里

### 17.4 旧框架只允许作为参考

允许参考旧框架的场景只有两类：

1. 参考 provider 的实际启动参数、环境变量、日志格式、会话文件字段
2. 参考某个已验证过的交互细节，例如 tmux pane 启动、session 绑定、resume 入口

不允许直接继承旧框架的内容：

- 目录兼容规则
- 模糊路径查找
- “先 fallback 再说”的错误恢复策略
- 多套 daemon 并存的运行时
- 为了兼容旧行为而保留的巨石入口

### 17.5 新框架的最小核心范围

新框架第一优先级只保留以下核心：

- 项目级配置解析
- agent 级身份与绑定
- workspace materialization
- 单一 askd
- provider execution
- completion
- storage
- cli

第一阶段建议只把以下 provider 视为核心公民：

- `codex`
- `claude`
- `gemini`

对 `opencode / droid / copilot / qwen / codebuddy`：

- 不再把“已能 degraded 跑起来”当作核心目标
- 可以保留 manifest / stub / fake fixture
- 但不应反向决定新框架的核心抽象

如果这些 provider 需要支持，应在主框架稳定后按独立 provider 包接入，而不是先污染公共边界

### 17.6 需要优先收敛的结构性问题

按重要性排序，当前最需要动刀的是：

1. 统一入口
   - `ccb` 应收敛为单一 v2 入口
   - phase1 应退出默认路径，最终删除

2. 删除 compatibility 模型
   - `AgentSpec` 不应再包含 `compatibility_mode`
   - `CompletionManifest` 不应继续围绕 `supports_legacy_quiet_fallback` 设计

3. 清理路径层 legacy
   - `session_utils.py` 只认 `.ccb/`
   - session 文件只认项目级 `.ccb/` 与 agent 级命名

4. 清理 terminal 兼容层
   - `TmuxBackend` / `WeztermBackend` 只接受明确 runtime target
   - 不再混用 pane id、session name、window target

5. 砍掉旧 askd adapter 双轨
   - `askd/adapters/*` 与 `provider_execution/*` 不应长期共存为两套主实现
   - 新框架只保留 `provider_execution/*`

6. provider 范围收缩
   - 先锁定 `codex / claude / gemini`
   - 其它 provider 退到次级目录或插件化入口

### 17.7 推荐的执行顺序

Immediate

- 冻结新框架边界：只允许 v2 主路径继续演进
- 在文档中明确旧框架“仅参考、不兼容、不兜底”
- 标记所有 legacy 模块为待删除对象

Next

- 删除 `CompatibilityMode` 及相关 manifest 字段
- 把 `session_utils.py` 收敛到 `.ccb/` 单路径
- 把 `terminal.py` 的 legacy tmux session 兼容接口拆掉
- 让 `ccb` 只走 phase2

Later

- 移除 `askd/adapters/*` 这套旧桥接层
- 将非核心 provider 下沉为插件式接入或暂时移出主框架范围
- 形成一个真正只包含 `cli -> askd -> provider_execution -> completion -> storage` 的内核

### 17.8 文件级删除清单

下列对象应视为“新框架优先删除或下沉”的目标：

- `lib/session_utils.py` 中所有 legacy 目录与根目录 session 查找逻辑
- `lib/terminal.py` 中 session-name 级 tmux 兼容发送逻辑
- `lib/askd/adapters/`
- `lib/laskd_daemon.py`
- 顶层 `bin/caskd` / `bin/gaskd` / `bin/oaskd` / `bin/daskd` / `bin/laskd` 所代表的旧心智
- `ccb` 中 phase1 入口与旧启动分支

说明：

- “删除”不等于立刻物理移除
- 可以先通过文档和模块注释将其标记为 non-core，然后分阶段移出运行时
- 但后续实现决策不得再依赖这些旧对象存在

### 17.9 新框架验收标准

当且仅当以下条件满足时，才能认为新框架足够干净：

- 新入口不再依赖 phase1
- 核心模型不再包含 compatibility/fallback 策略
- session 路径只认 `.ccb/`
- terminal runtime 不再接受 legacy target 语义
- askd 只面向项目级 agent-first runtime
- completion 不再为旧 marker 设计全局策略
- provider 核心抽象只由 `codex / claude / gemini` 的稳定需求驱动

如果做不到这些，就不应宣布“新框架已经完成 clean-cut 重构”。
