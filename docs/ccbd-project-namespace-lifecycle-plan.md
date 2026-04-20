# CCBD 项目级 Namespace 与生命周期详细改造方案

## 1. 文档定位

这份文档是项目控制面总纲的详细实施版，聚焦以下新目标：

- 每个 `.ccb` 项目拥有专属 tmux server/socket
- `ccbd` 是唯一项目 authority
- daemon、tmux namespace、agent runtime 形成强绑定生命周期
- `ccb` / `ccb kill` 语义彻底收敛

它是以下文档的细化与补充：

- `docs/ccbd-project-control-plane-refactor-plan.md`
- `docs/ccbd-startup-supervision-contract.md`
- `docs/ccbd-pane-recovery-continuous-attach-plan.md`

若旧文档中仍残留 shared/default tmux 假设、pane 枚举式 cleanup 假设、或 `start` 与 UI attach 混杂的表述，以本文为准。

本文不讨论 provider prompt/protocol，也不讨论 mail/message 语义重构；只定义项目控制面与 tmux 生命周期闭环。

## 2. 最终设计结论

### 2.1 最终判断

当前系统真正的问题不是“少几个探活”或“少几个 kill fallback”，而是 authority split。

当前实现里已经有一部分正确骨架：

- `.ccb/ccbd/` 已经是项目级状态根
- `lease + socket + heartbeat + startup lock` 已经接近唯一 backend authority
- pane ownership 已经开始记录 `@ccb_project_id` / `@ccb_agent`

但主链路仍然混着两套目标：

1. 项目控制面 authority
2. 把 agent pane 嵌进用户当前 tmux 交互世界

这两套目标混在一起，直接导致：

- `start_flow` 同时编排 workspace、tmux 布局、runtime 复用、binding 回写、cleanup
- `kill` 仍主要依赖 pane/pid 枚举和 best-effort 扫尾
- pane 仍被当成半个 routing key，而不是 namespace 内的从属资源

### 2.2 目标模型

最终模型固定为：

```text
一个 .ccb 项目
  = 一个 project identity
  = 一个 ccbd authority
  = 一个 keeper
  = 一个专属 tmux server/socket
  = 一个 namespace epoch
  = 一组固定 agent slot
```

关键结论：

- tmux server/socket 必须成为项目 namespace 的正式组成部分
- `ccbd` 必须成为 tmux namespace 的唯一 owner
- `pane_id` 只能是观测事实，不能再是 runtime authority 主键
- `ccb kill` 的主语义必须是销毁项目 namespace，而不是清点 pane

### 2.3 CLI 最终语义

最终用户语义固定如下：

- `ccb`
  - 负责 ensure 项目 backend、ensure 项目 namespace、ensure 配置内 agent 已挂载
  - 交互式调用在 start transaction 成功后 attach 到该项目专属 tmux server
  - 非交互式调用只输出 start transaction 状态，不 attach
- `ccb kill`
  - 停止 `ccbd`
  - 停止 keeper 重启
  - 销毁项目专属 tmux server
  - 终止所有项目 agent/runtime
  - 结束后项目 namespace 必须不存在

这套语义允许多个项目并行运行，因为每个项目都有独立 tmux socket/server。

## 3. 当前代码的结构性问题

### 3.1 启动路径仍然耦合 shared tmux

当前主问题点：

- `lib/ccbd/start_flow.py`
- `lib/cli/services/tmux_start_layout.py`
- `lib/cli/services/runtime_launch_runtime/tmux_runtime.py`

具体表现：

- `start_flow` 既在做 authority 事务，又在做交互式 tmux layout
- `prepare_tmux_start_layout()` 依赖当前 pane 并围绕其 split
- `launch_tmux_runtime()` 仍保留“当前 pane 启动失败 -> detached session fallback”的 shared tmux 兼容逻辑

这说明当前启动模型默认把“当前 terminal/tmux 环境”当成 runtime 资源宿主，而不是把“项目 namespace”当成 runtime 宿主。

### 3.2 停止路径的抽象层级错误

当前主问题点：

- `lib/cli/services/kill.py`
- `lib/cli/services/tmux_project_cleanup.py`
- `lib/ccbd/supervisor.py`

具体表现：

- `kill` 先收集 tmux socket、pane、pid，再做 cleanup
- `stop_all()` 仍按 agent/runtime 枚举收尾，而不是先摧毁 namespace
- `cleanup_project_tmux_orphans_by_socket()` 仍是正常关停主路径的一部分

这本质上说明系统还把 tmux 当成“外部环境里的一堆 pane”，而不是项目内部受控命名空间。

### 3.3 runtime identity 仍然不稳定

当前主问题点：

- `lib/terminal_runtime/tmux_identity.py`
- `lib/provider_core/tmux_ownership.py`
- `lib/ccbd/services/health.py`

具体表现：

- ownership 主要靠 `@ccb_project_id` + `@ccb_agent`
- `runtime.json` 里记录了 `pane_id` 和 `tmux_socket_name`
- 但没有“slot identity”和“namespace epoch”概念

后果：

- 同名 agent 重启、旧 pane 残留、tmux server 换代时，系统只能继续做更多存在性判断和 fallback，而不是直接判定旧资源无效。

### 3.4 `start` 和 `attach` 语义混名

当前主问题点：

- `lib/ccbd/socket_client.py`
- `lib/ccbd/services/runtime.py`
- `lib/cli/router.py`

具体表现：

- RPC 中的 `attach` 实际是注册 runtime binding，不是 UI attach
- CLI 生命周期已经收敛为 `ccb` foreground start，不能再新增独立 attach-only 管理命令
- 结果 `start` 需要清晰拆分为 startup transaction 与 foreground attach stage，避免和 binding 回写入口混淆

这会长期污染模块命名和调用者心智。

### 3.5 `askd` 残留会持续制造边界漂移

`PathLayout` 和部分兼容路径里仍保留大量 `askd_*` alias。

这不是当前第一优先级的可运行性问题，但它会持续稀释 `ccbd` 作为项目控制面的语义边界。后续改造必须把 `askd` 留在兼容层，不能再允许它参与新设计命名。

## 4. 目标架构

## 4.1 顶层分层

目标架构拆成六层：

1. `project bootstrap`
2. `ccbd authority`
3. `project namespace controller`
4. `runtime supervisor`
5. `provider facts adapter`
6. `ui attach layer`

其中：

- authority 决策只能发生在 1-4 层
- provider 层只能提供事实，不能拥有项目 authority
- UI attach 层只能消费 namespace，不能反向定义 namespace

### 4.1.1 project bootstrap

职责：

- 解析最近 `.ccb` anchor
- 加载 `.ccb/config.yaml`
- 生成 `project_root` / `project_id` / `PathLayout`

非职责：

- 不启动 tmux
- 不创建 pane
- 不决定 runtime 是否可复用

### 4.1.2 ccbd authority

职责：

- 唯一 backend authority
- lease/heartbeat/generation 管理
- RPC 入口
- 启动/停止事务边界

非职责：

- 不直接操作 provider-specific 启动细节
- 不持有 tmux 低层命令细节

### 4.1.3 project namespace controller

职责：

- 创建和销毁项目专属 tmux server/socket
- 创建和维护 slot layout
- 为 agent 分配固定 slot
- 对 `ccb` foreground attach stage 提供 namespace facts

非职责：

- 不决定 provider session 语义
- 不直接决定 agent 业务状态

### 4.1.4 runtime supervisor

职责：

- 按 desired agents reconcile slot 和 runtime
- 在 slot 缺失、pane 死亡、provider 退出时执行恢复
- 统一写 runtime authority

非职责：

- 不围绕当前 shell/tmux 环境做布局
- 不做 blind search

### 4.1.5 provider facts adapter

职责：

- 提供 provider-specific start command
- 提取 session facts
- 提供 provider-specific recover hooks

非职责：

- 不决定项目 identity
- 不决定 tmux namespace
- 不直接写项目 authority

### 4.1.6 ui attach layer

职责：

- attach/switch 到项目 tmux session
- 如果需要，可输出会话名和 socket path 给 CLI

非职责：

- 不启动 agent
- 不做 runtime binding 回写

## 4.2 项目 namespace 定义

项目 namespace 由以下资源组成：

- `.ccb/ccbd/lease.json`
- `.ccb/ccbd/ccbd.sock`
- `.ccb/ccbd/state.json`
- `.ccb/ccbd/tmux.sock`
- `.ccb/ccbd/lifecycle.jsonl`
- `.ccb/ccbd/startup-report.json`
- `.ccb/ccbd/shutdown-report.json`
- `.ccb/ccbd/supervision.jsonl`

逻辑上再加两个内存态概念：

- `namespace_epoch`
- `slot map`

### 4.2.1 namespace_epoch

它表示当前 tmux namespace 世代号。

规则：

- 每次成功创建全新项目 tmux namespace 时递增
- runtime authority、tmux user options、report 都记录该值
- 旧 epoch 的 pane/session 一律视为 stale evidence

这样做的直接收益是：

- 不需要在旧 pane 和新 pane 之间做复杂猜测
- kill/restart 后的旧 pane 即便物理残留，也不会再被误认为当前 authority

### 4.2.2 agent slot

每个 configured agent 拥有一个稳定的 slot：

- `slot_key = agent:<agent_name>`

slot 是逻辑身份，不等于 `pane_id`。

`pane_id` 可以变化，slot 不变化。

`runtime.json` 记录的是：

- 这个 agent 当前绑定到哪个 slot
- 该 slot 当前对应的 pane/session 是什么

## 5. 状态与记录契约

## 5.1 PathLayout 必须新增的路径

`lib/storage/paths.py` 需要正式增加以下访问器：

- `ccbd_state_path`
- `ccbd_tmux_socket_path`
- `ccbd_lifecycle_log_path`
- `ccbd_tmux_session_name`

推荐规则：

- `ccbd_tmux_socket_path = .ccb/ccbd/tmux.sock`
- `ccbd_tmux_session_name = ccb-<project-slug>`

设计原则：

- tmux endpoint 不能再靠环境变量或 runtime 推断
- 它必须从 `PathLayout(project_root)` 可直接计算

## 5.2 `.ccb/ccbd/state.json`

新增并固定以下字段：

- `project_id`
- `namespace_epoch`
- `tmux_socket_path`
- `tmux_session_name`
- `layout_version`
- `ui_attachable`
- `last_started_at`
- `last_destroyed_at`
- `last_destroy_reason`

用途：

- 作为项目 namespace 的静态描述和最近一次切换记录
- 给 `doctor` / `logs` / foreground attach 使用

## 5.3 `.ccb/agents/<agent>/runtime.json`

必须补齐并固定以下字段：

- `agent_name`
- `project_id`
- `provider`
- `workspace_path`
- `slot_key`
- `namespace_epoch`
- `terminal_backend`
- `tmux_socket_path`
- `tmux_session_name`
- `pane_id`
- `session_file`
- `session_id`
- `runtime_root`
- `runtime_pid`
- `health`
- `lifecycle_state`
- `desired_state`
- `reconcile_state`
- `managed_by`
- `last_seen_at`

约束：

- `pane_id` 丢失不等于 authority 丢失
- `namespace_epoch` 不匹配时，该 runtime 必须直接视为 stale

## 5.4 tmux pane user options

每个项目受管 pane 必须带上至少这些 user options：

- `@ccb_project_id`
- `@ccb_agent`
- `@ccb_slot`
- `@ccb_namespace_epoch`
- `@ccb_role`
- `@ccb_managed_by`

建议取值：

- `@ccb_role = cmd | agent`
- `@ccb_managed_by = ccbd`

ownership 校验必须至少比对：

- `project_id`
- `slot`
- `namespace_epoch`

`agent_name` 只能作为语义标签，不能单独充当 ownership 主键。

## 5.5 生命周期日志

新增统一日志：

- `.ccb/ccbd/lifecycle.jsonl`

最少记录以下事件：

- `daemon_started`
- `namespace_created`
- `slot_created`
- `slot_recreated`
- `runtime_spawned`
- `runtime_rebound`
- `runtime_exit_detected`
- `recover_started`
- `recover_succeeded`
- `recover_failed`
- `kill_started`
- `namespace_destroyed`
- `daemon_stopped`

这份日志的目标不是给用户读，而是为了支持现场定位和系统性复盘。

## 6. 命令语义重构

## 6.1 `ccb`

最终只做 ensure，不做 attach。

事务顺序固定为：

1. resolve project
2. ensure keeper
3. ensure `ccbd`
4. ensure namespace
5. ensure desired agent slots
6. ensure desired agents mounted
7. persist startup report
8. 返回结构化状态

成功时的含义必须收紧为：

- `ccbd` 健康
- 项目 tmux namespace 已存在
- desired agents 已达到 `healthy` 或 `recovering`

## 6.2 `ccb` foreground attach

foreground attach 是 `ccb` start transaction 的末端阶段，不是独立管理命令。

语义固定为：

- attach 前必须完成正常 `ccb` start transaction
- attach 不创建独立 authority
- attach 不重写 startup report
- attach 必须 select 当前 workspace window

如果 namespace 不存在：

- 返回明确错误
- 提示先执行 `ccb`

## 6.3 `ccb kill`

主语义固定为：

1. 写入 shutdown intent
2. 停止 keeper 自动拉起
3. 停止 `ccbd` intake 与 reconcile
4. 停止所有 configured agents
5. 销毁项目 tmux namespace
6. 清空 runtime authority 到 stopped/unmounted
7. unmount lease
8. 输出 shutdown report

正常主路径必须优先做：

- `kill-server` 或 session-destruction

而不是：

- pane 列举
- orphan cleanup
- pid 猜测

### 6.3.1 关于错误活着的 pane

新的系统目标不是“永远能修掉所有历史错误 pane”，而是“默认设计里不会再产生 authority 误判的活着 pane”。

因此：

- 项目主路径只管理项目专属 tmux socket 下的资源
- shared/default tmux 中的历史残留不再属于项目生命周期的一部分
- 若要清理历史残留，可放到 `doctor` 或一次性迁移工具，不进入正常 `kill` 语义

## 7. 模块与文件改造表

| 当前文件 | 当前问题 | 改造动作 | 目标结果 |
| --- | --- | --- | --- |
| `lib/storage/paths.py` | 缺少项目级 tmux endpoint；`askd_*` 兼容名仍混在主路径 | 增加 `ccbd_state_path`、`ccbd_tmux_socket_path`、`ccbd_lifecycle_log_path` 等；新代码禁止再读 `askd_*` | namespace 可以从路径层直接解析 |
| `lib/cli/services/daemon.py` | daemon 启动逻辑仍没有显式 namespace 概念 | 保留 lease/keeper/ccbd 启动职责；tmux 创建与销毁移交 namespace controller | daemon 层只处理 authority，不处理 pane cleanup |
| `lib/ccbd/start_flow.py` | 事务太胖，混合 workspace/materialize/binding/tmux/cleanup | 拆成 `prepare_start_context`、`ensure_namespace`、`mount_agent`、`record_startup_report` | 启动路径变成可理解的固定流程 |
| `lib/cli/services/tmux_start_layout.py` | 依赖当前 pane split；是 shared tmux 世界观 | 从主路径移除；保留历史兼容时迁移到 legacy/doctor | 正常启动不再耦合当前 tmux |
| `lib/cli/services/runtime_launch_runtime/tmux_runtime.py` | 还在做 shared pane 启动和 detached fallback | 改成“在指定项目 namespace 的指定 slot 内 respawn” | runtime launch 只依赖项目 namespace |
| `lib/cli/services/tmux_project_cleanup.py` | 正常主路径依赖 pane 枚举和 orphan kill | 降级为 diagnostics/fallback 工具，不参与正常 start/kill | kill 不再靠 pane scavenging |
| `lib/cli/services/kill.py` | 仍在猜 socket/pid/pane | 主路径调用 `stop_all + destroy_namespace`；fallback 仅在 daemon 不可达时使用 | `ccb kill` 变成 namespace destruction |
| `lib/ccbd/supervisor.py` | `stop_all()` 仍按 runtime 枚举清理 | stop 逻辑改为“先 freeze runtime，再 destroy namespace，再写 stopped state” | 关停路径对 tmux server 有原子控制 |
| `lib/ccbd/services/health.py` | 仍围绕 pane/session 事实做较细碎的 rebind 推断 | 改为 namespace/slot-first 健康模型 | 恢复分支变短，判断更稳定 |
| `lib/ccbd/supervision/loop.py` | 仍以 runtime 记录为起点，而不是 slot 期望状态 | 以 desired agent slots 为起点重写 reconcile | pane 死亡时自动重建 slot 与 runtime |
| `lib/terminal_runtime/tmux_identity.py` | 缺少 slot 和 epoch 标签 | 新增 `@ccb_slot` / `@ccb_namespace_epoch` / `@ccb_managed_by` | ownership 可严格校验 |
| `lib/provider_core/tmux_ownership.py` | ownership 校验粒度不够 | 把 project + slot + epoch 作为强校验字段 | 旧 pane 不会再被误吸收 |
| `lib/ccbd/socket_client.py` | `attach` 命名误导 | 把运行时注册 RPC 重命名为 `register_runtime` 或 `upsert_runtime_binding` | RPC 语义和 UI attach 解耦 |
| `lib/cli/router.py` / `lib/cli/phase2.py` | 旧设计曾把 UI attach 拆成独立命令 | 保持 `ccb` 为唯一 start/restore/attach 入口，attach-only 命令不进入 parser/dispatch | CLI 生命周期稳定 |

## 8. 需要新增的模块

## 8.1 `lib/ccbd/services/project_namespace.py`

这是本轮重构的核心新增模块。

职责：

- 读取/写入 namespace state
- 创建项目专属 tmux server/socket
- 确保基础 layout 存在
- 提供 slot 确保与销毁接口

建议 API：

```python
@dataclass(frozen=True)
class ProjectNamespace:
    project_id: str
    namespace_epoch: int
    tmux_socket_path: str
    tmux_session_name: str
    layout_version: int


@dataclass(frozen=True)
class NamespaceSlot:
    slot_key: str
    agent_name: str | None
    pane_id: str | None
    role: str


def load_namespace(layout) -> ProjectNamespace | None: ...
def ensure_namespace(layout, project_id: str, *, recreate: bool = False) -> ProjectNamespace: ...
def ensure_agent_slot(namespace: ProjectNamespace, agent_name: str) -> NamespaceSlot: ...
def attach_namespace(namespace: ProjectNamespace) -> None: ...
def destroy_namespace(namespace: ProjectNamespace, *, force: bool = False) -> dict: ...
```

## 8.2 `lib/ccbd/services/project_namespace_state.py`

职责：

- 读写 `.ccb/ccbd/state.json`
- 管理 `namespace_epoch`
- 管理最近一次 namespace 创建/销毁记录

设计要求：

- 只做 state I/O
- 不直接调用 tmux 命令

## 8.3 `lib/cli/services/start_foreground.py`

职责：

- `ccb` foreground attach 阶段的主实现
- attach/switch 到项目 tmux server
- 返回 foreground attach 会话信息给调用方

设计要求：

- 不改变 agent desired state
- 不直接写 runtime authority

## 8.4 `lib/ccbd/services/runtime_registration.py`

职责：

- 收敛当前 `attach` 的运行时注册语义
- 给 runtime supervisor 提供唯一 upsert 入口

设计要求：

- 明确区分“注册 runtime authority”和“attach UI”

## 9. 函数级重构约束

## 9.1 `run_start_flow()` 必须被拆开

当前 `run_start_flow()` 责任过载，必须拆分成至少四个稳定步骤：

1. `prepare_start_context()`
2. `ensure_project_namespace()`
3. `mount_or_rebind_agent()`
4. `persist_startup_report()`

禁止继续在一个函数内同时承担：

- workspace materialize
- tmux layout split
- stale binding 推断
- orphan cleanup
- runtime attach 回写

## 9.2 `_prepare_start_layout()` 必须退出主路径

当前 `_prepare_start_layout()` 的 shared tmux 假设与目标设计冲突。

处理方式：

- 主路径中删除
- 若需历史兼容，迁移到 `legacy` 或 `doctor` 相关文件

## 9.3 `launch_tmux_runtime()` 必须改签名

它不应再接受“无约束 backend_factory + assigned_pane_id 可有可无”的接口。

改造方向：

```python
def launch_tmux_runtime(
    *,
    namespace: ProjectNamespace,
    slot: NamespaceSlot,
    spec,
    plan,
    launcher,
    pane_title_marker_fn,
    write_session_file_fn,
) -> RuntimeLaunchResult: ...
```

新约束：

- backend 必须显式绑定项目 tmux socket
- slot 必须先于 runtime launch 存在
- 不再支持 detached fallback session

## 9.4 `cleanup_project_tmux_orphans_by_socket()` 必须退位

它可以保留，但角色只能是：

- doctor
- migration cleanup
- forced fallback

不能再作为：

- 正常启动后的主 cleanup
- 正常 kill 的主 cleanup

## 9.5 `stop_all()` 必须先 destroy namespace

`lib/ccbd/supervisor.py` 的 `stop_all()` 需要调整事务顺序。

目标顺序：

1. 冻结 runtime reconcile
2. 标记 shutdown intent
3. 停止 agent 执行
4. destroy namespace
5. upsert runtime stopped
6. persist shutdown report

只有在 `destroy namespace` 失败时，才允许进入 forced residue cleanup。

## 9.6 `HealthMonitor` 必须从 pane-first 改为 slot-first

目标判断顺序：

1. 当前 runtime 的 `namespace_epoch` 是否匹配
2. 项目 namespace 是否存在
3. slot 是否存在并 ownership 正确
4. slot 内 pane 是否活着
5. provider session 是否仍可用于 rebind
6. 否则按标准 mount path 重建

这会显著减少当前“missing / foreign / dead / session-missing”的分支蔓延。

## 9.7 `RuntimeSupervisionLoop` 必须从 desired slots 出发

它的主循环不应再问“这个 runtime 记录看起来怎样”，而应先问：

- 配置要求哪些 agent 存在
- 这些 agent 的 slot 是否存在
- 这些 slot 的当前 pane/runtime 是否满足契约

这样 supervisor 就真正拥有“没有任何 pane 挂在前台，也必须自动恢复”的能力。

## 10. 实施阶段

## 10.1 Phase A: Namespace 契约落地

交付物：

- `PathLayout` 新增 tmux namespace 路径
- `.ccb/ccbd/state.json`
- `ProjectNamespace` / `ProjectNamespaceState`

门禁：

- 任意项目都能稳定计算 tmux socket path 和 session name
- 不再依赖 `CCB_TMUX_SOCKET` 作为 authority 输入

## 10.2 Phase B: CLI 语义拆分

交付物：

- `ccb` 主命令说明收敛为“start/restore/attach project UI”
- attach-only public command 不进入 parser/dispatch
- RPC 命名中避免把 foreground attach 表达成独立 lifecycle command

门禁：

- 非交互式 `ccb` 不 attach UI 仍能成功启动
- 交互式 `ccb` 在 start 成功后 attach

## 10.3 Phase C: Slot 与 Epoch 改造

交付物：

- runtime.json 新增 `slot_key` / `namespace_epoch`
- tmux user options 新增 `@ccb_slot` / `@ccb_namespace_epoch`
- ownership 检查升级

门禁：

- 旧 pane 无法在新 epoch 下被误识别为当前 authority
- agent 重启后 slot 稳定而 `pane_id` 可变化

## 10.4 Phase D: Start 路径收敛

交付物：

- `run_start_flow()` 拆分
- 删除主路径中的 `prepare_tmux_start_layout()`
- `launch_tmux_runtime()` 改为 slot-based launch

门禁：

- 不在 tmux 内执行 `ccb` 也能正确启动
- 在 tmux 内执行 `ccb` 不再修改用户当前布局

## 10.5 Phase E: Kill 路径收敛

交付物：

- `destroy_namespace()` 落地
- `kill_project()` 主路径重写
- `stop_all()` 先销毁 namespace 再写 stopped state

门禁：

- `ccb kill` 后项目专属 tmux server 不存在
- `ccb kill` 后所有 configured agents 都进入 stopped/unmounted

## 10.6 Phase F: Supervision 重写

交付物：

- slot-first `HealthMonitor`
- desired-slot-first `RuntimeSupervisionLoop`
- pane 死亡后的后台自动重建

门禁：

- agent pane 手工 kill 后，无需新命令即可自动恢复
- `ccbd` crash 后 keeper 恢复后仍能正确接管当前 namespace

## 10.7 Phase G: 报告与日志统一

交付物：

- `lifecycle.jsonl`
- startup/shutdown report 新字段
- `doctor`/`logs` 可以读取 lifecycle 记录

门禁：

- 任何“启动失败 / 恢复失败 / kill 异常”都能从 `.ccb/ccbd/` 内定位

## 10.8 Phase H: 旧路径退场

必须退出主路径的旧逻辑：

- shared/default tmux assumptions
- detached fallback session
- `tmux_project_cleanup` 主路径依赖
- `attach` 作为 runtime 注册命名
- 新代码读取 `askd_*` alias

## 11. 测试矩阵

## 11.1 启动场景

- `.ccb` 不存在
- `.ccb` 存在但为空
- `.ccb/config.yaml` 缺失
- config 合法但 backend 未启动
- config 改变但旧 backend 仍存活
- backend crash，keeper 自动恢复

## 11.2 tmux namespace 场景

- 项目首次启动，创建新 tmux server/socket
- 在普通 shell 内执行 `ccb`
- 在 tmux 内执行 `ccb`
- 重复执行 `ccb` attach 到已存在 namespace
- 两个不同项目并行启动，socket/server 完全隔离

## 11.3 pane 与 slot 场景

- agent pane 正常存活
- agent pane 被 kill
- agent pane 变 foreign
- slot 缺失但 namespace 仍在
- provider session 缺失但 slot 仍在

## 11.4 kill 与重启场景

- 正常 `ccb kill`
- `ccb kill` 时当前前台没有任何 pane
- `ccb kill -f`
- kill 后立即再次 `ccb`
- kill 后旧 default tmux 残留 pane 不影响新启动

## 11.5 日志与报告场景

- 启动成功
- 启动失败
- recover 成功
- recover 失败
- kill 成功
- kill 失败后 forced residue cleanup

## 12. 非目标与取舍

## 12.1 明确放弃的能力

本方案明确不再把以下目标作为默认能力：

- 自动把 agent pane 嵌入用户当前 tmux layout
- 用 pane blind search 修正所有历史共享 tmux 遗留物
- 继续把 `pane_id` 当主身份

## 12.2 主要收益

这样做换来的收益是明确的：

- 一个项目拥有真正封闭的生命周期
- 多项目可并行运行且互不污染
- `kill` 可以做 namespace destruction，而不是 best-effort scavenging
- pane 死亡恢复可以依赖 slot/epoch，而不是更多猜测

## 13. 完成标准

只有同时满足以下条件，这轮架构改造才算完成：

1. `ccb` 不再隐式操作当前 tmux 布局
2. 每个项目都拥有专属 tmux socket/server
3. `ccb kill` 结束后项目 namespace 不存在
4. pane 死亡可由 daemon 后台自动恢复
5. `.ccb/ccbd/` 内的报告与日志足以定位生命周期问题
6. 新主路径不再依赖 pane blind search、shared default tmux、或 `askd` 兼容命名

达到这六条后，项目控制面才算从“能工作但靠很多分支兜住”转为“结构上稳定闭环”。
