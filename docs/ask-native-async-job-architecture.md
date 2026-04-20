# Ask Native Async Job 新架构方案

> 历史说明：本文写于旧双后端阶段。凡文中出现的 WezTerm/双后端描述，都不是当前主仓权威实现；当前运行时已经收口为 tmux-only，未来原生 Windows 方向请看 `docs/ccbd-windows-psmux-plan.md`。

## 1. 文档目的

这份文档定义 `bin/ask` 的最终形态：

- `ask` 默认就是后台异步提交
- 异步能力来自 `askd` 原生 job 模型
- 不再通过 shell / PowerShell 临时脚本做 detached 包装
- 不再保留旧 TCP `UnifiedAskDaemon`
- 不再把 `pend` 作为主链路的一部分
- 保留 `pend`，但只作为辅助观察入口，不参与 ask 主流程或完成判断

这不是兼容迁移方案，而是**纯净 cutover 方案**。

本方案明确接受以下事实：

- 旧内部实现可以被删除
- CLI 行为可以被重定义
- 不为历史双轨共存付出架构复杂度

## 2. 硬性决策

本方案采用以下不可回退的设计决策。

### 2.1 单一 askd 内核

仓库内只保留一套 askd 主内核：

```text
cli/bin -> AskdApp -> dispatcher -> provider_execution -> completion -> storage
```

保留：

- [`lib/askd/app.py`](/home/bfly/yunwei/ccb_source/lib/askd/app.py)
- [`lib/askd/socket_client.py`](/home/bfly/yunwei/ccb_source/lib/askd/socket_client.py)
- [`lib/askd/handlers/`](/home/bfly/yunwei/ccb_source/lib/askd/handlers)
- [`lib/askd/services/`](/home/bfly/yunwei/ccb_source/lib/askd/services)
- [`lib/provider_execution/`](/home/bfly/yunwei/ccb_source/lib/provider_execution)

退役：

- [`lib/askd/daemon.py`](/home/bfly/yunwei/ccb_source/lib/askd/daemon.py)
- [`lib/askd/daemon_runtime/`](/home/bfly/yunwei/ccb_source/lib/askd/daemon_runtime)
- [`lib/askd/server.py`](/home/bfly/yunwei/ccb_source/lib/askd/server.py) 及其旧 TCP 使用面
- `bin/askd` 所代表的旧 TCP ask daemon 路径
- `bin/ask` 中临时 `.sh/.ps1` 后台包装逻辑

### 2.2 异步是默认语义，不再是特判

`ask` 默认行为统一为：

- 提交 job
- 立即返回 `job_id`
- 后续通过 `watch/get/cancel` 观察或控制

不再保留：

- “只有某个 caller 默认异步”的特判
- `--background` 这种把异步当成附加模式的思路
- shell detach 后再递归调用一次 `ask --foreground`

### 2.3 `pend` 退出主路径，但不删除

最终主路径只有：

- `submit`
- `watch`
- `get`
- `cancel`

`pend` 不是主流程动作，也不应影响 LLM 判断。

这里要明确区分两类语义：

- provider `pend` / `cpend` / `gpend` / `lpend`
  - 作用：读取 provider session 中最近 N 轮消息
  - 定位：人工查看、调试、排查
  - 约束：不进入 ask 主链路，不参与完成判断
- `ccb pend`
  - 作用：读取 askd/job 当前状态与 latest decision
  - 定位：agent-first 项目级状态查看
  - 约束：它是观测接口，不是 provider session 回读器

本方案的最终目标是：

- `pend` 退出主链路
- `pend` 保留为辅助观察入口
- “查看最新回复”统一通过 `get(job_id)` 或 `watch(job_id)` 完成

### 2.3.1 当前落地状态

截至 2026-03-27，这条主线已经收敛到以下形态：

- [`bin/ask`](/home/bfly/yunwei/ccb_source/bin/ask) 已经是 askd native job client
- provider submit wrappers 已退出 ask 主链路
  公开提交面现在只接受 agent 目标；遗留 wrapper 仅保留为报错提示壳
- [`bin/lask`](/home/bfly/yunwei/ccb_source/bin/lask) 的 `--no-wrap`
  不再依赖进程级环境变量旁路，而是通过 provider job 的
  `provider_options.no_wrap` 显式下传到 Claude execution 层
- `pend` 仍保留为人工辅助查看入口，但已经与 ask 自动提交/自动回收主流程隔离

当前剩余工作已经不在 provider wrapper 主路径，而集中在旧
TCP daemon compat 层、若干旧测试、以及少量运维/诊断入口。

### 2.4 不做兼容层

本方案明确**不做**以下设计：

- 双 askd 并存
- compat adapter
- hidden overlay agent 仅为兼容旧命令而存在
- 旧 job 模型与新 job 模型并存
- `ask` 新旧异步路径可切换
- 长期保留旧 detached script 路线作为 fallback

切换完成后，只存在一条生产路径。

## 3. 现状问题

当前 `ask` 后台模式之所以不适合成为最终方案，不是因为它完全不能工作，而是因为它处在错误的层级。

当前问题集中在 [`bin/ask`](/home/bfly/yunwei/ccb_source/bin/ask)：

- 它自己决定前台/后台语义
- 它自己创建 task log 和 status file
- 它自己写 shell / PowerShell 临时脚本
- 它自己 detached 出一个子进程
- 子进程内部再调用一次 `ask --foreground`

这会带来四类长期问题：

### 3.1 异步不是第一类模型

当前后台只是一个 CLI 包装结果，不是 askd 的第一类执行对象。

因此以下能力都会变弱：

- 统一恢复
- 统一追踪
- 统一取消
- 统一状态观测
- 统一故障诊断

### 3.2 双 askd 模型污染边界

仓库已经有新的 `AskdApp + submit/get/watch` 体系，但 `bin/ask` 仍在走旧的 `UnifiedAskDaemon` 思路。

这会导致：

- 同一个项目存在两套异步模型
- 两套 job 生命周期概念并存
- 文档、测试、排障路径都变复杂

### 3.3 `pend` 容易被误当成主路径

当主链路没有把“提交后如何拿结果”统一收敛到 `watch/get` 时，`pend` 就容易被误用成补拉工具。

这会制造错误心智：

- 让人误以为系统依赖“事后再读一遍日志”
- 让 LLM 把 `pend` 当成业务步骤
- 让 completion 观测和 reply 读取混成一件事

### 3.4 当前异步语义不一致

现在的异步行为带 caller 特判，例如：

- 某些 caller 默认后台
- 其他 caller 默认前台

这不是稳定的系统规则，只是历史行为残留。

## 4. 最终目标架构

## 4.1 架构总图

最终只保留下面这条链路：

```text
bin/ask
  -> AskdSocketClient
  -> AskdApp
  -> JobDispatcher
  -> ProviderExecutionAdapter
  -> CompletionTracker
  -> Job/Snapshot/Event Storage
```

关键变化是：

- `ask` 不再“自己执行异步”
- `ask` 只做提交和可选观察
- 真正的异步运行、状态流转、完成判断全部收敛到 askd

## 4.2 当前 Target 结论

当前主线已经明确收敛到 agent-only public target：

- `TargetKind.PROVIDER` 已退出 askd 主链路
- 公共提交入口只接受 agent 名
- provider 只作为 agent 背后的 execution/completion backend 存在

因此后续扩展不再引入 provider-facing target 模型，而应在 agent-first 之上增加更强的 message / mailbox / coordination 语义。

- `ccb ask` 生成 `TargetKind=agent`
- `bin/ask` 生成 `TargetKind=agent`
- dispatcher、execution、completion、storage 围绕 agent-first target 统一收敛
- `agent_name` 是主路由键，provider 信息退到 backend/execution 元数据层

这一步是整个新架构的核心。

## 4.3 统一 Job 模型

当前 [`lib/askd/api_models_runtime/records.py`](/home/bfly/yunwei/ccb_source/lib/askd/api_models_runtime/records.py) 中的 `JobRecord` 偏向“agent job”。

目标是把它扩展为真正统一的 job record。

建议最终 `JobRecord` 至少包含：

- `job_id`
- `submission_id`
- `target_kind`
- `target_name`
- `provider`
- `provider_instance`
- `request`
- `status`
- `terminal_decision`
- `cancel_requested_at`
- `created_at`
- `updated_at`

其中：

- `target_name`
  - 对 agent job 是 `agent_name`
  - 对 provider job 是 `provider[:instance]`
- `provider`
  - 永远是 provider 真值，不再从 agent 间接推导

这样做的目的：

- 同一套 store 同时承载 agent job 与 provider job
- `watch/get/cancel` 不需要分叉
- `render` 层只根据 `target_kind` 决定显示样式

## 4.4 统一提交接口

askd 应提供两个一等入口，但都落到同一个 dispatcher/job core：

- `submit_agent`
- `submit_provider`

建议新增：

- `lib/askd/handlers/submit_provider.py`
- `AskdSocketClient.submit_provider(...)`

规则：

- `bin/ask` 应优先调用 `submit_agent`
- `bin/ask` 仅在显式 provider 模式下调用 `submit_provider`
- `ccb ask` 仍调用 `submit_agent`
- 两条入口都产出同一种 `SubmitReceipt`

这样是清晰的，因为：

- 命令面可以保持 agent-first
- 内核 job 模型相同

## 4.5 统一观察接口

最终只保留三类观察动作：

- `watch(job_id)`
- `get(job_id)`
- `get_latest(target)`

其中主路径是：

- 长时等待结果看 `watch(job_id)`
- 快速查状态看 `get(job_id)`

ask-native 主链路不依赖 `pend`。

但 `pend` 仍可保留为辅助命令，只是职责必须收敛：

- provider `pend`：查看最近 N 轮 provider session 消息
- `ccb pend`：查看 askd/job 状态

两者都不能承担“推动 ask 流程继续向前”的职责。

## 4.6 `bin/ask` 的最终职责

[`bin/ask`](/home/bfly/yunwei/ccb_source/bin/ask) 最终应退化成一个薄客户端。

它只做四件事：

1. 解析 CLI 参数
2. 生成 provider submit request
3. 调用 askd socket client
4. 根据子命令决定是立即返回还是 watch

它不再负责：

- 异步实现
- detached 启动
- log/status 文件维护
- 后台脚本生成
- provider 执行生命周期管理

## 5. 命令面重定义

为了得到纯净结构，本方案建议直接重定义 `ask` 命令面。

### 5.1 默认提交

```bash
ask <provider[:instance]> -- <message...>
```

行为：

- 创建 provider job
- 输出 `ask_status: accepted`
- 输出 `job_id`
- 输出 `provider`
- 输出 `target`
- 立即退出

### 5.2 阻塞等待

```bash
ask wait <job_id>
```

或：

```bash
ask <provider[:instance]> --wait -- <message...>
```

行为：

- 如果是 `wait <job_id>`，直接 watch 到 terminal
- 如果是 `--wait`，先 submit，再 watch 到 terminal

注意：

- `--wait` 只是 submit 之后立刻 watch
- 它不是另一套执行模式

### 5.3 状态查看

```bash
ask get <job_id>
ask cancel <job_id>
```

### 5.4 删除旧标志

以下标志或语义应删除：

- `--background`
- `--foreground`
- `--notify` 的旧特殊路径
- caller 特判异步默认值
- 输出 task log/status file 路径

其中 completion hook 的 fallback 通知已经不再走旧 `--notify`
旁路，而是统一回到 `ask --agent --mode notify`。

### 5.5 退役旧命令

以下命令面应从最终架构中退役：

- `cask`
- `gask`
- `lask`
- `oask`
- `dask`
- 其他 provider-specific `*ask` wrapper

`pend` 保留为辅助诊断/历史查看入口，但不再承担 ask 自动回收、
完成态判定或主提交流程职责。

## 6. 目录与模块职责

## 6.1 `bin/`

- `bin/ask`
  - provider job 提交与观察客户端
- `bin/ccb`
  - agent job 提交与观察客户端

删除 `ask` 的 detached script 逻辑后，`bin/` 层不再承载执行编排。

## 6.2 `lib/askd/`

保留并强化以下职责：

- socket server
- submit/get/watch/cancel handlers
- dispatcher
- job store / event store / snapshot store
- completion polling
- health / ownership / mount

新增职责：

- provider submit handler
- target model
- target resolver

## 6.3 `lib/provider_execution/`

保留为唯一 provider 执行入口。

它负责：

- 启动 provider turn
- 轮询 completion source
- 生成 terminal decision
- 恢复与 replay

它不再与旧 ask daemon adapter 并存。

## 6.4 `lib/provider_backends/<provider>/`

保持 provider 私有差异集中在 backend slice 中：

- session lookup
- prompt wrapping
- runtime binding
- log/session reader
- provider-specific completion extraction

这样可以继续保持 agent-first / shared-first 核心的干净边界。

## 6.5 平台与终端后端边界

这个新架构必须显式考虑不同系统实现：

- Windows 主要走 WezTerm
- Linux / macOS 主要走 tmux

这会影响 provider turn 的真实投递方式，但**不应该影响 `ask` 的异步架构本身**。

### 平台差异真正应该落在哪一层

平台差异只允许存在于以下两层：

- terminal backend 层
- runtime binding / session binding 层

对应现有代码：

- [`lib/terminal.py`](/home/bfly/yunwei/ccb_source/lib/terminal.py)
- [`lib/provider_execution/common.py`](/home/bfly/yunwei/ccb_source/lib/provider_execution/common.py)
- provider backend 自己的 `session.py / execution.py`

例如当前 provider execution 已经是按这个方向设计的：

- provider adapter 通过 [`terminal.get_backend_for_session()`](/home/bfly/yunwei/ccb_source/lib/terminal.py#L132) 解析后端
- 执行发送与存活检测通过 [`send_prompt_to_runtime_target()`](/home/bfly/yunwei/ccb_source/lib/provider_execution/common.py#L95) 和 [`is_runtime_target_alive()`](/home/bfly/yunwei/ccb_source/lib/provider_execution/common.py#L107) 走统一 helper

这说明：

- `tmux` 和 `wezterm` 差异已经有正确的落点
- `ask` job 化本身不需要知道当前是 Windows 还是 Linux

### 新架构中的硬性规则

实施时必须坚持下面几条规则。

#### 规则 1. `bin/ask` 不得感知 tmux / wezterm

[`bin/ask`](/home/bfly/yunwei/ccb_source/bin/ask) 只能做：

- submit
- watch
- get
- cancel

它不得再包含：

- tmux 特判
- wezterm 特判
- Windows / Unix 下不同异步实现
- detached shell / PowerShell 分支

也就是说，切掉旧后台脚本后，`bin/ask` 的平台差异应该趋近于零。

#### 规则 2. runtime context 必须显式表达 backend 类型

不论是 agent job 还是 provider job，最终进入 execution service 时都必须带统一 runtime context。

至少要稳定包含：

- `workspace_path`
- `backend_type`
- `runtime_ref`
- `session_ref`
- `runtime_pid`
- `runtime_health`

现有 [`ProviderRuntimeContext`](/home/bfly/yunwei/ccb_source/lib/provider_execution/base.py#L15) 已经接近这个目标，后续应继续强化，而不是让 provider 侧重新自行猜测平台。

#### 规则 3. pane target 是统一抽象，不是平台分支

`tmux` 和 `wezterm` 底层 target 格式不同，但 execution 层只应该处理“runtime target”。

例如：

- tmux 用 pane id
- wezterm 用 pane / tab 运行时引用

这些差异由 terminal backend 解释，不进入 `askd` job 模型。

#### 规则 4. provider session 解析允许平台差异，但不能穿透到 job 模型

不同 provider 在不同系统上的 session 元数据可能不同，例如：

- Windows 下 WezTerm runtime 信息
- Unix 下 tmux pane/session 信息

这些差异应停留在：

- `provider_backends/<provider>/session.py`
- `provider_backends/<provider>/execution.py`
- runtime binding resolver

不能把 job record 重新做成“tmux job”和“wezterm job”两套。

### 对实施步骤的影响

这意味着实施时要额外补做两件事。

第一，在 Step 4 中，runtime binding resolver 不只是“从 agent/provider 找到上下文”，还必须把终端后端差异标准化。

建议 Step 4 的产出固定为：

- `provider`
- `instance`
- `workspace_path`
- `backend_type`
- `runtime_ref`
- `session_ref`
- `runtime_pid`
- `runtime_health`

第二，在 Step 5 中，provider execution adapter 只能依赖统一 helper 与 runtime context，不允许直接在 adapter 内新增 `if windows` / `if tmux` 这种横向分支。

### 验收补充

这个方案完成后，必须增加平台边界验收项：

- Windows + WezTerm 下 `ask submit/watch/get/cancel` 行为与 Linux/macOS 一致
- `bin/ask` 代码中不再包含平台特化异步分支
- provider execution 只通过 terminal backend helper 与 runtime context 使用平台差异
- 系统测试不能再把平台差异和异步模型耦合在一起

## 7. 明确删除清单

切换完成后，应明确删除下列内容，而不是保留在仓库里“以防万一”。

### 7.1 删除旧 ask daemon

- [`lib/askd/daemon.py`](/home/bfly/yunwei/ccb_source/lib/askd/daemon.py)
- [`lib/askd/daemon_runtime/`](/home/bfly/yunwei/ccb_source/lib/askd/daemon_runtime)
- 与旧 TCP ask daemon 绑定的入口、测试和文档

### 7.2 删除 `bin/ask` 后台脚本包装

删除 [`bin/ask`](/home/bfly/yunwei/ccb_source/bin/ask) 中以下逻辑：

- task status file
- task log file
- `.sh` / `.ps1` 临时脚本生成
- detached `Popen` 执行
- 递归 `ask --foreground`

### 7.3 删除 `pend` 命令族

- `bin/pend`
- `bin/cpend`
- `bin/gpend`
- `bin/lpend`
- 其他 provider-specific `*pend`

### 7.4 删除旧 caller 特判逻辑

删除 `ask` 中“caller 决定默认前后台模式”的逻辑。

最终规则必须是：

- 默认 submit
- 显式 wait/watch

## 8. 实施步骤

以下步骤按严格顺序执行，不做双轨共存。

### Step 1. 重建 askd Target 模型

目标：

- 在 `askd` API 模型层引入 `TargetKind` / `TargetRef`
- 让 `JobRecord` 不再只绑定 `agent_name`

需要修改：

- [`lib/askd/api_models_runtime/messages.py`](/home/bfly/yunwei/ccb_source/lib/askd/api_models_runtime/messages.py)
- [`lib/askd/api_models_runtime/records.py`](/home/bfly/yunwei/ccb_source/lib/askd/api_models_runtime/records.py)
- [`lib/askd/api_models_runtime/receipts.py`](/home/bfly/yunwei/ccb_source/lib/askd/api_models_runtime/receipts.py)

完成标准：

- job 模型能同时表达 agent job 与 provider job
- `render/get/watch` 不再假设 target 一定是 agent

### Step 2. 引入 provider submit handler

目标：

- 让 `askd` 原生接受 provider job 提交

新增：

- `lib/askd/handlers/submit_provider.py`
- `lib/askd/services/provider_targeting.py`

需要修改：

- [`lib/askd/app.py`](/home/bfly/yunwei/ccb_source/lib/askd/app.py)
- [`lib/askd/socket_client.py`](/home/bfly/yunwei/ccb_source/lib/askd/socket_client.py)

完成标准：

- `AskdSocketClient.submit_provider()` 可以返回标准 `SubmitReceipt`
- provider submit 直接进入统一 dispatcher

### Step 3. 把 dispatcher 从 agent-only 改成 target-aware

目标：

- dispatcher 能处理两类 target

需要修改：

- [`lib/askd/services/dispatcher.py`](/home/bfly/yunwei/ccb_source/lib/askd/services/dispatcher.py)
- [`lib/askd/services/dispatcher_runtime/lifecycle.py`](/home/bfly/yunwei/ccb_source/lib/askd/services/dispatcher_runtime/lifecycle.py)
- [`lib/askd/services/dispatcher_runtime/context.py`](/home/bfly/yunwei/ccb_source/lib/askd/services/dispatcher_runtime/context.py)
- [`lib/askd/services/dispatcher_runtime/routing.py`](/home/bfly/yunwei/ccb_source/lib/askd/services/dispatcher_runtime/routing.py)

完成标准：

- `submit_agent` 与 `submit_provider` 共用一套 job 生命周期
- `watch/get/cancel` 不区分来源

### Step 4. 重建 runtime binding 解析

目标：

- 不再从 agent 名间接推 provider 执行上下文
- provider job 直接解析运行时绑定和会话绑定

建议新增：

- `lib/askd/services/runtime_binding_resolver.py`

它负责输出统一 `RuntimeBindingContext`：

- `target_kind`
- `provider`
- `instance`
- `workspace_path`
- `runtime_ref`
- `session_ref`
- `backend_type`

完成标准：

- execution service 不再需要依赖“必须先有 agent runtime 才能执行”
- provider job 与 agent job 共用绑定上下文模型

### Step 5. 收敛 provider execution 为唯一执行入口

目标：

- 只保留 [`lib/provider_execution/`](/home/bfly/yunwei/ccb_source/lib/provider_execution) 作为 provider turn 执行路径

需要修改：

- provider execution adapter 的入参模型
- completion polling 逻辑
- restore / replay 的 persisted state

完成标准：

- provider job 不再走旧 ask daemon adapter
- completion、cancel、restore 统一基于 execution service

### Step 6. 重写 `bin/ask`

目标：

- 让 `bin/ask` 成为纯客户端

需要修改：

- [`bin/ask`](/home/bfly/yunwei/ccb_source/bin/ask)

重写后行为：

- `ask <provider> -- <message>` -> submit provider job
- `ask wait <job_id>` -> watch
- `ask get <job_id>` -> get
- `ask cancel <job_id>` -> cancel

删除：

- detached shell/PowerShell
- task log/status file
- caller 特判前后台

完成标准：

- `bin/ask` 中不再包含临时脚本生成逻辑
- `bin/ask` 中不再包含独立异步执行逻辑

### Step 7. 隔离 `pend` 语义

目标：

- ask 主链路只保留 `watch/get`
- 保留 `pend`，但不让它污染 ask 主链路

需要修改：

- 明确 provider-specific `pend` 只读取最近 N 轮 provider session 消息
- 明确 `ccb pend` 只读取 askd/job 状态
- 删除所有把 `pend` 当成 ask 主链路步骤的提示、模板和文档
- 更新系统测试和文档

完成标准：

- ask 主链路不再需要 `pend`
- LLM 指令模板中不再把 `pend` 当成业务步骤
- provider `pend` 仍可独立用于人工查看最近 N 轮消息
- `ccb pend` 仍可独立用于项目级 job 状态查看

### Step 8. 删除旧 TCP ask daemon

目标：

- 仓库里不再存在第二套 ask 异步内核

需要删除：

- [`lib/askd/daemon.py`](/home/bfly/yunwei/ccb_source/lib/askd/daemon.py)
- [`lib/askd/daemon_runtime/`](/home/bfly/yunwei/ccb_source/lib/askd/daemon_runtime)
- 旧 TCP ask daemon 的入口脚本、测试、文档引用

完成标准：

- 代码搜索不再出现 `UnifiedAskDaemon`
- `bin/ask` 不再引用旧 ask daemon 状态文件或 TCP 请求协议

## 9. 测试与验收标准

切换完成后，至少满足以下验收条件。

### 9.1 命令行为

- `ask <provider> -- <message>` 总是立即返回 `job_id`
- `ask wait <job_id>` 能稳定拿到 terminal reply
- `ask get <job_id>` 能返回当前状态与最终 reply
- `ask cancel <job_id>` 能取消尚未完成的 job

### 9.2 架构纯度

- 仓库内只有一套 askd 异步内核
- 仓库内没有 detached script 异步逻辑
- 仓库内的 `pend` 不再承担 ask 主链路职责
- 仓库内没有 caller 特判前后台逻辑

### 9.3 稳定性

- askd 重启后 job snapshot / restore 正常
- provider session rotate 不会导致 reply 丢失
- cancel / failed / incomplete 状态能统一进入 terminal decision
- system tests 不再依赖 `pend` 验证 reply

### 9.4 可观测性

- reply、completion_reason、completion_confidence 都可通过 `get/watch` 获得
- 不需要再看 `ask-*.status` 之类 CLI 包装文件

## 10. 非目标

本方案不追求以下事项：

- 保留旧 `ask` 前后台标志的兼容语义
- 为没有项目上下文的历史脚本继续保留旧 ask daemon
- 在 provider job 上继续伪装成 agent job
- 保留 `pend` 作为辅助观察入口

## 11. 最终判断

这次重构的关键不是“让 `bin/ask` 的后台脚本更稳”，而是让 `bin/ask` **失去后台实现职责**。

真正应该稳定的对象是：

- askd 的 job 模型
- provider execution
- completion tracking
- watch/get/cancel 的统一状态面

一旦完成本方案，`ask` 的异步将不再是脚本技巧，而是系统核心能力。
