# CCBD Windows 原生 `psmux` 适配详细方案

## 1. 文档定位

这份文档定义 `ccb_source` 在原生 Windows 下，基于 `psmux` 实现与当前 tmux 版本尽量一致的项目控制面方案。

它是以下文档的补充设计，而不是替代：

- `docs/ccbd-startup-supervision-contract.md`
- `docs/ccbd-diagnostics-contract.md`
- `docs/ccb-config-layout-contract.md`
- `docs/ccbd-project-namespace-lifecycle-plan.md`

其中：

- 上述 contract 文档仍然是当前行为的 authoritative source
- 本文负责定义 Windows 落地路线、平台边界、模块拆分和实施 phase
- 当 Windows 方案真正落地并改变主契约时，必须反向更新 contract 文档，而不是只改本文

本文目标不是引入新的平台特判散落在系统各处，而是把 Windows 支持收束到清晰的后端边界内。

## 2. 目标与非目标

### 2.1 目标

Windows 版本必须尽量保持与当前 tmux 版本相同的核心语义：

- 一个 `.ccb` 项目对应一个唯一 `ccbd`
- 一个项目拥有一个独立的 mux namespace
- `.ccb/ccb.config` 继续作为唯一配置 authority
- `ccb` 继续是 ensure backend + ensure namespace + ensure desired agents + interactive foreground attach
- `ccb kill` 继续是项目级销毁语义
- pane 死亡后由 daemon supervision 自动恢复
- namespace 级恢复后，pane 位置回到 `.ccb/ccb.config` 定义的 canonical layout
- pane 标题、颜色、布局、agent 命名继续以 `.ccb/ccb.config` 为准
- 关闭当前终端窗口时，后台 namespace 和 agent 继续存活

### 2.2 非目标

本文不追求：

- 在第一阶段实现 100% tmux 命令兼容
- 在第一阶段支持 Windows Terminal / WezTerm / `psmux` 三套并存主路径
- 在第一阶段重写 provider 协议或 session 读取逻辑
- 把 Windows 支持做成分散的 `if windows` 补丁集合
- 用 `psmux` 事实反向定义项目 authority

## 3. 为什么选 `psmux`

### 3.1 结论

如果目标是“原生 Windows 下尽量接近当前 tmux 版本”，`psmux` 是当前最合适的 mux 基座。

原因：

- 它本质上是 Windows native 的 tmux-family 多路复用器
- 它直接建立在 Windows `ConPTY` 之上
- 它对 tmux 命令语言和 `.tmux.conf` 有较高兼容度
- 它保留 session/pane/split/send-keys/attach 这类关键 tmux 语义
- 它比 Windows Terminal 更接近“后台多路复用内核”
- 它比 WezTerm 更接近“沿用当前 tmux 控制模型”

### 3.2 为什么不是 Windows Terminal

Windows Terminal 的本质是 terminal host，不是项目级后台 mux authority。

它可以：

- 开 tab
- 开 pane
- 记住部分 layout

但它不天然承担：

- 项目级唯一 namespace
- 项目级 session authority
- daemon supervision 友好的 pane control surface
- 与 `ccb kill` 一致的项目级生命周期收口

### 3.3 为什么不是第一阶段直接走 WezTerm

WezTerm 功能很强，也有自己的 mux server，但它不是 tmux-family 语义。

如果第一阶段直接切到 WezTerm，代价不是“换一个终端后端”，而是：

- 重新定义 pane/session/runtime 的控制方式
- 重新定义 attach / layout / send-text / capture 语义
- 在大量现有 tmux 假设上做整体迁移

这会显著放大 Windows 适配成本。

因此本文的路线是：

- 短期：Windows 以 `psmux` 作为 tmux-family backend
- 中期：把上层从“直接依赖 tmux CLI 细节”重构成“依赖 mux backend contract”
- 长期：如果 `psmux` 局部不满足要求，再补 Windows-native backend，而不是重写整个控制面

## 4. 最终设计原则

### 4.1 平台差异只允许落在后端层

Windows 支持不能穿透到以下层级：

- CLI 命令语义
- `ccbd` authority 模型
- `.ccb/ccb.config` 语义
- supervisor 恢复状态机
- provider 业务状态机

平台差异只允许显式存在于：

- mux backend 层
- runtime binding 层
- Windows IPC 层
- Windows 进程树生命周期层

### 4.2 `psmux` 只是 mux，实现 authority 的仍然是 `ccbd`

`psmux` 负责：

- session
- pane
- split
- attach/detach
- title/style
- send-text
- capture

`ccbd` 负责：

- 项目级唯一 authority
- desired agents 计算
- runtime supervision
- pane 死亡恢复
- `ccb kill` 项目级收口
- authority 状态持久化

不能允许：

- 从 `psmux` 当前有哪些 pane 反推项目真相
- 从残留 session 反推配置 authority
- 从 provider session 文件反向定义 namespace

### 4.3 Windows 版本必须保持“强封闭生命周期”

Windows 版不能退化成“只是能开几个 pane”。

最终目标仍然是：

```text
一个 .ccb 项目
  = 一个 project identity
  = 一个 ccbd authority
  = 一个项目级 psmux namespace
  = 一组配置定义的 agent slot
  = 一组受 supervision 的 runtime
  = 一个项目级 kill / recover / reopen 生命周期闭环
```

## 5. Windows 版最终架构

## 5.1 顶层模型

Windows 版建议固定为：

```text
ccb CLI
  -> ccbd (project authority)
  -> mux backend contract
       -> psmux backend
  -> windows ipc contract
       -> named pipe
  -> windows runtime ownership
       -> job objects
```

等价映射：

- Linux/macOS:
  - `ccbd + tmux + unix socket`
- Windows native:
  - `ccbd + psmux + named pipe + job object`

### 5.2 三个核心资源

每个 Windows 项目至少拥有三类独立资源：

1. backend authority
   - `ccbd`
   - `lease.json`
   - startup lock
   - heartbeat
2. mux namespace
   - `psmux` server/session
   - pane layout
   - title/style/layout version
3. process tree ownership
   - 每个 provider runtime 对应 job object
   - `kill` 时可结束整棵 provider 进程树

三者关系：

- `ccbd` 拥有 namespace
- namespace 承载 pane
- pane 运行 provider 主进程
- provider 主进程与其子进程受 job object 约束

### 5.3 不能只把 pane 当作生命体

Windows 上尤其不能把“pane 还在”当成“runtime 一定健康”。

必须明确：

- pane 是 UI/mux 事实
- provider 进程树是执行事实
- runtime authority 由 `ccbd` 持有

因此 Windows 版必须双层治理：

- `psmux` 负责 pane/session 事实
- `Job Object` 负责进程树生死

## 6. 后端抽象改造方案

### 6.1 从 `terminal backend` 提升到 `mux backend`

当前代码已有 `terminal_runtime` 抽象，但很多地方仍然默认 “tmux pane id + tmux socket + tmux CLI”。

Windows 方案落地前，建议先把抽象从“终端”收束成“多路复用后端能力”。

推荐分成两层：

- `backend_family`
  - `tmux`
- `backend_impl`
  - `tmux`
  - `psmux`

这样做的目的：

- 当前 tmux 路径与 Windows `psmux` 共享同一个 family 语义
- 诊断层能看出真实实现到底是 `tmux` 还是 `psmux`
- 不会把 `psmux` 伪装成完全等同的 Unix tmux

补充约束：

- 当前主仓实现已经收口为 tmux-only，不再保留 WezTerm 作为并行 backend
- Windows 原生恢复时，不允许再把 WezTerm 当成过渡主路径

### 6.2 `mux backend` 最小能力契约

Windows 首期落地前，应明确后端 contract 至少要覆盖：

- `ensure_namespace()`
- `destroy_namespace()`
- `attach_namespace()`
- `namespace_exists()`
- `list_panes()`
- `describe_pane()`
- `split_pane()`
- `kill_pane()`
- `send_text()`
- `capture_pane()`
- `set_pane_title()`
- `set_pane_user_option()`
- `set_pane_style()`
- `pane_alive()`
- `session_alive()`
- `apply_ui_contract()`

如果某项能力在 `psmux` 缺失，必须显式记录为 capability gap，不准在主链路中偷偷依赖。

### 6.3 新的后端分类建议

建议新增：

- `MuxBackend`
- `TmuxFamilyBackend`
- `TmuxBackend`
- `PsmuxBackend`
- `WeztermBackend`

关系：

- `TmuxBackend` 和 `PsmuxBackend` 共享大部分 tmux-family 语义
- `WeztermBackend` 继续作为独立 family
- 上层控制流尽量只依赖 `MuxBackend`

### 6.4 当前代码需要重点收口的位置

优先收口这些文件中的 tmux 假设：

- `lib/terminal_runtime/backend_types.py`
- `lib/terminal_runtime/api.py`
- `lib/terminal_runtime/tmux_backend.py`
- `lib/terminal_runtime/layouts.py`
- `lib/provider_execution/common.py`
- `lib/ccbd/supervisor.py`
- `lib/ccbd/services/health.py`
- `lib/ccbd/supervision/loop.py`
- `lib/cli/services/runtime_launch.py`
- `lib/cli/services/tmux_ui.py`

收口目标：

- 上层不再直接假设 `tmux sock path`
- 上层不再直接假设 `pane_id` 一定是 Unix tmux 形式
- 上层不再直接假设 shell 一定是 bash 风格 quoting

## 7. Windows IPC 方案

### 7.1 不能沿用 Unix socket 假设

Windows 版不能继续把 backend IPC 主语义建立在 `.sock` 文件上。

建议改为显式 IPC 抽象：

- `ipc_kind`
  - `unix_socket`
  - `named_pipe`
- `ipc_ref`
  - socket path 或 pipe name

### 7.2 持久化建议

`.ccb/ccbd/` 下建议新增或强化以下文件：

- `lease.json`
- `start-policy.json`
- `namespace.json`
- `ipc.json`
- `lifecycle.jsonl`

其中：

- `lease.json`
  - backend authority、generation、owner pid
- `start-policy.json`
  - `-a` 继承策略、restore 规则
- `namespace.json`
  - namespace implementation、session name、layout version、backend family
- `ipc.json`
  - `ipc_kind`、`ipc_ref`
- `lifecycle.jsonl`
  - 启动、恢复、kill、reflow、异常退出、job kill 记录

### 7.3 Windows 下的 pipe 命名建议

不要把 named pipe 名称直接散落在代码各处。

建议统一生成规则：

- 基于 `project_id`
- 加入产品前缀，例如 `ccb-`
- 保证多项目并行时互不冲突

例如：

- `\\\\.\\pipe\\ccb-<project_id>-ccbd`

具体命名规则应由统一 path/service 负责，不允许调用方拼接字符串。

## 8. Windows 进程树治理方案

### 8.1 为什么必须引入 Job Object

原生 Windows 上，如果只 kill pane 或只关 terminal，不能保证 provider 子进程树一定干净退出。

这会直接破坏：

- `ccb kill` 的封闭生命周期语义
- pane 死亡后的恢复判断
- diagnostics 对真实残留的识别

因此，Windows 版每个 runtime 建议引入 job object。

### 8.2 运行模型

每个 agent runtime 启动时：

1. 创建或绑定一个 job object
2. 启动 provider 主进程
3. 把 provider 主进程及其子进程树纳入 job
4. 将 job identity 写入 runtime authority

### 8.3 `ccb kill` 的 Windows 收口顺序

Windows 下 `ccb kill` 推荐顺序：

1. `ccbd` 进入 stopping 状态
2. 停止 supervision loop
3. 对每个 configured runtime 执行 job kill
4. 销毁项目 namespace
5. 停止 backend IPC
6. 清理 `start-policy.json`
7. 清理 lease/heartbeat 等运行态

关键点：

- pane kill 不是主收口手段
- pane/session cleanup 是 namespace 销毁的一部分
- process tree kill 由 job object 负责

### 8.4 恢复与 job object 的关系

pane 死亡恢复不能只看 pane。

恢复判断至少应检查：

- pane 是否还活着
- session 是否还活着
- provider 主进程是否仍在 job 中
- job 是否已退出
- 当前 runtime authority 是否仍属于本 generation

## 9. Namespace 与布局方案

### 9.1 核心原则

Windows 版必须继续遵守当前 layout contract：

- `.ccb/ccb.config` 是唯一布局 authority
- `cmd` 是前台 anchor pane
- pane 标题必须以逻辑名显示
- pane 死亡恢复后位置必须回到 canonical layout

### 9.2 `psmux` namespace 要求

第一阶段必须验证 `psmux` 是否满足以下能力：

- 项目级独立 server/session
- attach / reattach
- `split-window`
- `kill-pane`
- `kill-session`
- `send-keys`
- `capture-pane`
- pane title
- pane user options 或等价 marker
- session-scoped UI options

如果 `psmux` 不能提供项目级独立 server，而只能共享一个 global server，则 Windows 版仍可推进，但需要明确降级为：

- `shared server + project session`

这会削弱“每个项目专属 namespace”的强度，因此应作为显式降级方案，而不是默认方案。

### 9.3 布局恢复原则不变

Windows 版继续沿用现有恢复契约：

1. health check 只做观测，不做隐式修复
2. supervision loop 拥有恢复 authority
3. pane 死亡优先 project namespace reflow
4. reflow 不安全时，才做局部 pane recreate
5. 恢复完成后必须重新应用 UI contract

### 9.4 UI contract 的 Windows 约束

`psmux` 版本的 UI contract 需要尽量对齐 tmux 版本：

- pane title = `.ccb/ccb.config` 逻辑名
- pane border label = 逻辑名
- pane color identity 稳定
- session-scoped theme 每次 namespace ensure/reflow 都要重放
- provider-specific internal marker 不能覆盖可见标题

如果某些 tmux UI option 在 `psmux` 不兼容，必须通过 capability table 明确记录，而不是静默失效。

## 10. Runtime Authority 与存储变更

### 10.1 runtime authority 应新增字段

建议运行态 authority 至少增加以下字段：

- `backend_family`
- `backend_impl`
- `namespace_ref`
- `session_name`
- `pane_id`
- `ipc_kind`
- `ipc_ref`
- `job_id`
- `job_owner_pid`
- `layout_version`

### 10.2 authority 与 evidence 的边界

Windows 版必须继续保持：

authority:

- `.ccb/ccb.config`
- `lease.json`
- `start-policy.json`
- 当前 generation 的 `runtime.json`

evidence:

- `psmux` pane/session facts
- provider session files
- provider pid facts
- job object state

residue:

- 残留 session
- 残留 pane
- 残留 provider session 文件
- 失效 job 记录

job object 也只是 evidence，不允许反向重定义 authority。

## 11. Diagnostics 与日志方案

### 11.1 doctor / bundle 必须显式展示平台实现

Windows 版 diagnostics 应明确包含：

- `backend_family`
- `backend_impl`
- `namespace_backend`
- `ipc_kind`
- `ipc_ref`
- `job_count`
- `job_health`
- `namespace_health`
- `layout_version`
- `reflow_last_at`
- `recovery_last_reason`

### 11.2 bundle 应增加的材料

建议 diagnostics bundle 增加：

- `namespace.json`
- `ipc.json`
- `lifecycle.jsonl`
- `job-runtime/*.json`
- `psmux-doctor.txt`
- `psmux-list-panes.txt`
- `psmux-list-sessions.txt`

### 11.3 事件日志建议

至少记录以下事件：

- backend_start
- backend_takeover
- namespace_create
- namespace_recreate
- pane_recovery
- local_pane_recreate
- job_attach
- job_kill
- kill_begin
- kill_complete
- backend_crash
- backend_restart

日志必须能支撑：

- 用户上传 bundle 后复盘具体生命周期
- 判断是 namespace 问题还是 provider 进程树问题
- 判断 `ccb kill` 是否真正执行到了项目封口

## 12. `psmux` 能力闸门

在正式开发前，必须做一轮 Windows 真机 capability gate。

### 12.1 必测命令面

必须至少验证：

- `new-session`
- `attach-session`
- `switch-client`
- `split-window`
- `list-panes`
- `display-message`
- `kill-pane`
- `kill-session`
- `send-keys`
- `capture-pane`
- `set-option`
- `set-hook`
- `pipe-pane`

### 12.2 必测语义面

必须至少验证：

- 关闭当前 terminal 后 session 是否继续存活
- pane 死亡后 session 是否仍然可控
- 多项目并行时 namespace 是否互相隔离
- pane 标题是否稳定
- pane marker / user option 是否可读回
- attach 后 UI contract 是否仍可重复应用
- session 重建后 pane id 是否可重新发现

### 12.3 闸门结果分类

对每项能力要明确分类：

- `required`
- `supported`
- `partial`
- `unsupported`
- `workaround_available`

没有 capability report 之前，不应进入实现 phase。

## 13. 分阶段实施方案

### P0. Windows `psmux` capability 探针

目标：

- 在 Windows 真机上摸清 `psmux` 是否足以承载项目 namespace 模型

产物：

- capability report
- blackbox probe 脚本
- 明确的 gap list

退出标准：

- 核心 required 能力全部 `supported` 或有可接受 workaround

### P1. 抽象层收口

目标：

- 把当前代码中分散的 tmux 假设收束到 `mux backend contract`

动作：

- 重构 `terminal_runtime` 抽象
- 引入 `backend_family` / `backend_impl`
- 清理上层直接拼 `tmux` 命令或 `sock` 假设

退出标准：

- 上层主链路不再直接依赖 Unix tmux 特性名

### P2. Windows IPC 与 runtime ownership

目标：

- 加入 named pipe 与 job object 支撑

动作：

- 新增 Windows IPC service
- 新增 job object service
- 扩展 runtime authority schema
- 扩展 diagnostics

退出标准：

- Windows 下 backend 通信不再依赖 socket 文件
- `kill` 可明确终止 provider 进程树

### P3. `PsmuxBackend` 实现

目标：

- 在 `mux backend contract` 下实现 `psmux` backend

动作：

- session/pane/list/split/send/capture/title/style/attach 封装
- PowerShell quoting 收口
- capability-based feature degrade

退出标准：

- namespace 创建、attach、pane 操作可通过统一接口完成

### P4. Windows namespace lifecycle 接入

目标：

- 让 Windows 版 `ccbd` 真实跑在 `psmux` namespace 上

动作：

- ensure namespace
- destroy namespace
- layout projection
- reflow recovery
- foreground attach/kill 接入

退出标准：

- `ccb` / `ccb kill` 在 Windows 下形成闭环

### P5. Supervision 与黑盒稳定性

目标：

- 把现有 Linux 版的 supervision contract 复用到 Windows

动作：

- pane death recovery
- namespace reflow
- backend crash recovery
- start-policy 继承
- diagnostics bundle 校验

退出标准：

- 黑盒行为与当前 tmux 版语义一致

### P6. 文档与契约升级

目标：

- 将 Windows 支持从“设计计划”升级为正式 contract 的一部分

动作：

- 更新 startup contract
- 更新 diagnostics contract
- 更新 config/layout contract
- 增加 Windows 测试矩阵说明

退出标准：

- authoritative 文档与实现一致

## 14. 测试矩阵

### 14.1 启动与附着

必须覆盖：

- 空项目首次 `ccb`
- 已存在 backend 的 `ccb`
- 关闭 terminal 后重新 `ccb`
- 两个不同项目并行启动

### 14.2 恢复与 supervision

必须覆盖：

- pane 死亡且其他 agent idle
- pane 死亡且其他 agent busy
- provider 主进程退出但 pane 残留
- pane 残留但 runtime authority 已过代
- backend crash 后 keeper/restart

### 14.3 kill 与清理

必须覆盖：

- `ccb kill` 正常关闭
- `ccb kill` 后 namespace 不存在
- `ccb kill` 后 provider 子进程树消失
- `ccb kill` 后 start-policy 被清除
- kill 后再次启动能干净重建

### 14.4 布局与 UI

必须覆盖：

- 默认 2+2 布局
- `ccb.config` 自定义布局
- pane 标题与配置一致
- pane 颜色稳定
- pane 恢复后重新回到 canonical 位置

### 14.5 diagnostics

必须覆盖：

- doctor 输出 Windows backend 信息
- bundle 包含 namespace/job/pipe 元数据
- lifecycle log 可定位 recover/kill 路径

## 15. 风险与应对

### 15.1 `psmux` 能力差异风险

风险：

- 某些 tmux option 或 hook 在 `psmux` 上不完全兼容

应对：

- capability gate 先行
- capability table 驱动 degrade
- 不让缺失能力在主链路中静默失败

### 15.2 PowerShell / shell quoting 风险

风险：

- `send-keys`、命令包装、路径引用在 Windows shell 下行为不同

应对：

- quoting 必须集中到 Windows 专用 helper
- 禁止业务层拼接 PowerShell 字符串

### 15.3 pane 与进程树脱钩风险

风险：

- pane 看起来还在，但 provider 子进程树已经异常

应对：

- 引入 job object 作为第二生命信号
- health model 同时看 pane/session/job/runtime generation

### 15.4 共享 server 降级风险

风险：

- 如果 `psmux` 无法稳定提供项目级独立 namespace，只能退回共享 server

应对：

- 作为显式 fallback 方案记录
- 诊断输出必须明确说明是降级模式

## 16. 最终验收标准

Windows `psmux` 版只有在以下条件全部成立时，才算达到“接近当前 tmux 版”的目标：

- `ccb` 能 ensure backend、namespace、desired agents，并在交互式终端 attach 到项目 namespace
- `ccb kill` 能结束 backend、namespace、provider 进程树
- 关闭 terminal 后后台仍存活
- pane 死亡后 daemon 能自动恢复
- 恢复后布局回到 `.ccb/ccb.config` 定义的位置
- pane 标题与配置逻辑名一致
- diagnostics 能完整报告 Windows backend、job、pipe、namespace 状态
- 多项目可并行运行且互不串扰
- Windows 支持不依赖散落的 `if windows` 修补路径

## 17. 推荐的下一步

真正开始开发前，建议先做两件事：

1. 在 Windows 真机上完成 `psmux` capability gate，并把报告落盘
2. 在当前仓库先完成 `mux backend contract` 收口，再进行 Windows 实装

原因：

- 没有 capability gate，就无法判断 `psmux` 能否承担项目级 namespace
- 没有 contract 收口，Windows 实现会迅速退化成平台补丁集合

本文的核心结论可以压缩为一句话：

`psmux` 适合做 Windows 下最接近 tmux 的 mux 基座，但 `ccb` 的稳定性仍然必须建立在 `ccbd authority + project namespace + named pipe + job object` 这套封闭生命周期模型之上。
