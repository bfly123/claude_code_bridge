# CCBD 生命周期稳定性与时序收敛方案

## 1. 文档定位

这份文档是项目级 `ccbd` 生命周期、keeper 启停权、socket 绑定、显式 `kill` 语义、以及 provider helper ownership 的详细设计方案。

它补充并细化以下契约文档：

- `docs/ccbd-startup-supervision-contract.md`
- `docs/ccbd-project-namespace-lifecycle-plan.md`
- `docs/codex-session-isolation-contract.md`

若旧实现或旧计划仍允许：

- CLI 与 keeper 同时直接启动 `ccbd`
- `mounted` 出现在 socket ready 之前
- 显式 `ccb kill` 被 `socket_unreachable` 的 `degraded` 状态阻断
- provider helper/bridge 在失去 owner 后长期存活

则以后本文为目标设计，contract 需在实现同步落地时一起回写。

## 2. 设计结论

### 2.1 当前根因

当前问题不是个别 `kill` 分支或个别 `codex bridge` 回收漏掉，而是 authority split：

- project lifecycle authority 分散在 CLI、keeper、`lease.json`、socket 可连接性、heartbeat 观测之间
- provider runtime ownership 分散在 pane、runtime 记录、临时 helper 父进程、以及孤儿残留之间

这直接导致两类坏状态：

1. `pid_alive=true`、`heartbeat_fresh=true`、`socket_unreachable=true`
   - 普通 `ccb kill` 被错误阻断
   - `ccb ask`/`ccb` 只能看到 “进程活着但不可接管”的矛盾状态
2. provider helper/bridge 与 slot/runtime generation 解绑
   - `PPID=1` 的孤儿 bridge 长期堆积
   - 单个项目能反复拉起大量无主后台进程
   - 最终形成 CPU 调度风暴与 swap 压力

3. 冷启动 `ccb ask` 把慢启动误判为失败
   - `ask` 首次请求本质上只是想等 control-plane ready 并提交任务
   - 但当前实现把 keeper 拉起、`ccbd` bootstrap、socket readiness、以及本地 CLI deadline 混在一条短预算链路里
   - 结果是“稍慢但正确”的冷启动会先被本地等待方判成超时，随后 backend 才在后台完成 mounted

冷启动 `ask` 超时的主因不是通用 `CcbdClient` 默认 timeout 太短，而是生命周期预算语义错误：

- keeper 启动事务预算
- CLI 等待预算
- 单次 RPC probe timeout
- foreground attach timeout

这四类预算目前边界不清，导致实现层容易把“冷启动事务上限”错误地落在“通用 socket client 默认 timeout”上。

### 2.2 最终目标

最终架构固定为：

```text
一个 .ccb 项目
  = 一个 project lifecycle authority
  = 一个 keeper
  = 一个 authoritative ccbd generation
  = 一个 project namespace
  = 一组 slot-owned agent runtimes
  = 一组必须可回收的 provider helper groups
```

关键结论：

- keeper 是项目生命周期唯一推进者
- CLI 只能表达启动/停机意图，不能直接与 keeper 竞争 `ccbd` 启动权
- `mounted` 只能表示 control-plane 已 ready
- 冷启动 `ask` 只等待 control-plane readiness，不等待 namespace attachability 或全量 desired-agent recovery
- 显式 `ccb kill` 是强管理动作，不能被 “degraded but heartbeat fresh” 拒绝
- 所有长期 provider helper 都必须绑定到 slot runtime generation，并具备组级回收 authority

## 3. 生命周期分层

### 3.1 Project Lifecycle Plane

project lifecycle plane 由 keeper 独占 authority。

keeper 负责：

- 维护项目目标状态 `desired_state`
- 推进项目 phase
- 分配新的 backend generation
- 串行化 start/stop/restart 事务
- 观察当前 generation 是否成功 mounted 或进入 failed

keeper 不负责：

- 直接定义 agent provider session 语义
- 定义 pane 内业务状态
- 作为长期 backend 对外服务

### 3.2 Control Plane Execution

`ccbd` 是项目 control-plane 的执行者，不是生命周期 authority 的拥有者。

`ccbd` 负责：

- bind/listen project socket
- 对外提供 RPC
- 恢复/监督项目 namespace
- 维护 desired agent 的 runtime reconcile
- 刷新自身 lease heartbeat

`ccbd` 不负责：

- 判定项目是否“应该启动”
- 在失去 authority 后清理新 generation 的资源

### 3.3 Agent Runtime Plane

每个逻辑 agent slot 是独立 runtime ownership 单元。

一个 slot runtime 必须拥有：

- `slot_key`
- `runtime generation`
- `pane/window/workspace binding`
- `provider-state` 路径
- `provider helper group` 记录

slot runtime 是长期 helper/bridge 的唯一 owner。

### 3.4 CLI Plane

CLI 只负责：

- 解析项目
- 确保 keeper 存在
- 写入 lifecycle intent
- 等待 lifecycle phase 转移
- 在交互式 `ccb` 中执行 foreground attach

CLI 不再直接拥有 `spawn_ccbd_process()` 的 authority。

## 4. Authority Records

### 4.1 lifecycle.json

新增：

- `.ccb/ccbd/lifecycle.json`

这是 keeper-owned 的项目级 authority 记录。

最小字段：

- `project_id`
- `desired_state`
- `phase`
- `generation`
- `startup_id`
- `keeper_pid`
- `owner_pid`
- `owner_daemon_instance_id`
- `config_signature`
- `socket_path`
- `socket_inode`
- `namespace_epoch`
- `phase_started_at`
- `startup_stage`
- `last_progress_at`
- `startup_deadline_at`
- `last_failure_reason`
- `shutdown_intent`

`lifecycle.json` 的职责：

- 说明项目“应该是什么状态”
- 说明当前 phase 是什么
- 说明当前 authoritative generation 是哪个
- 为 CLI/keeper/ccbd 提供统一事实来源

### 4.2 lease.json

保留：

- `.ccb/ccbd/lease.json`

但语义收窄为：

- 当前 `ccbd` 实例的 liveness authority

最小字段：

- `project_id`
- `ccbd_pid`
- `generation`
- `daemon_instance_id`
- `socket_path`
- `last_heartbeat_at`
- `mount_state`

`lease.json` 不再单独定义 project phase。

### 4.3 runtime.json

每个 agent：

- `.ccb/agents/<agent>/runtime.json`

必须表达 slot runtime authority，而不是仅记录 pane facts。

应包含：

- `slot_key`
- `daemon_generation`
- `runtime_generation`
- `desired_state`
- `state`
- `reconcile_state`
- `workspace_epoch`
- `window_id`
- `pane_id`
- `runtime_owner_pid`
- `runtime_owner_pgid`
- `provider_state_root`
- `binding_source`
- `last_failure_reason`

写入规则补充：

- slot runtime authority 必须由单一 authority 写路径落盘，不能由外层 health/queue/dispatcher patch 顺手改写 epoch 或 binding 字段
- state-only patch 只能修改运行态字段，例如 `state`、`health`、queue depth、reconcile 标记、last-seen 时间
- 任何已有 runtime record 的 authority 字段变更都必须显式走 authority write，而不是依赖普通 upsert 容错

### 4.4 helper.json

若 provider 需要长期 helper/bridge：

- `.ccb/agents/<agent>/helper.json`

最小字段：

- `agent_name`
- `runtime_generation`
- `helper_kind`
- `leader_pid`
- `pgid`
- `started_at`
- `owner_daemon_generation`
- `state`

任何长期 helper group 都必须可从这个 manifest 追溯 owner。

写入规则补充：

- helper manifest writer 只认 canonical `runtime_generation`
- 不允许为了兼容旧记录而在主写路径回退到 `binding_generation`
- 若当前 runtime authority 缺失 canonical generation，则应清除 helper manifest 或拒绝写入，而不是伪造 owner

## 5. Project Lifecycle State Machine

### 5.1 desired_state

固定为：

- `running`
- `stopped`

### 5.2 phase

固定为：

- `unmounted`
- `starting`
- `mounted`
- `stopping`
- `failed`

### 5.3 含义

- `unmounted`
  - 当前没有 authoritative `ccbd`
  - 项目控制面完整停机
- `starting`
  - keeper 已拥有启动事务
  - 当前 generation 尚未 ready
- `mounted`
  - 当前 generation 已完成 socket bind/listen 与 readiness
  - 当前 generation 是 authoritative backend
- `stopping`
  - 项目已进入停机事务
  - 新恢复/重拉必须被抑制
- `failed`
  - 最近一次启动或运行事务失败
  - keeper 仍保有恢复 authority

### 5.4 相位转移

正常启动：

- `unmounted -> starting -> mounted`
- `failed -> starting -> mounted`

正常停机：

- `mounted -> stopping -> unmounted`
- `starting -> stopping -> unmounted`

运行中重配或强制替换：

- `mounted -> stopping -> starting -> mounted`

启动失败：

- `starting -> failed`

运行时故障：

- `mounted -> failed`

## 6. 启动时序

### 6.1 唯一启动者

keeper 是 `ccbd` 唯一启动者。

CLI 不再直接 spawn `ccbd`。CLI 只负责：

1. ensure keeper running
2. 清除 shutdown intent
3. 写入 `desired_state=running`
4. 等待 keeper-owned `startup_id/generation` 事务结果

### 6.2 启动事务

启动事务必须串行化为：

1. keeper 获取 lifecycle lock
2. 读取 `lifecycle.json` 与 `lease.json`
3. 如果已有 `phase=mounted` 且 config 匹配，则直接复用
4. 如果 `phase=starting`，则等待现有启动事务完成或超时
5. 如果 `phase=stopping`，则等待 stop transaction 完成
6. keeper 分配新 `generation + startup_id`
7. keeper 写入 `phase=starting`
8. keeper spawn child `ccbd`
9. child 校验自身仍属于当前 `generation/startup_id`
10. child bind/listen socket
11. child 执行最小 readiness self-ping
12. child 写入 `lease.json`
13. keeper 或 child 将 `phase` promote 到 `mounted`
14. mounted 后才进入 namespace recovery 与 runtime restore

### 6.3 mounted 的严格含义

`mounted` 只能表示：

- socket 已经成功 bind/listen
- self-ping 已经成功
- 当前 generation 仍持有 authority
- 当前 generation 的 lease 已发布

禁止的旧行为：

- 先写 mounted，再尝试 listen
- socket 仅存在文件路径，但服务端尚未 ready 也算 mounted

### 6.4 readiness 分层

系统必须显式区分以下三层 readiness：

1. control-plane readiness
   - 当前 authoritative generation 已 bind/listen project socket
   - 当前 authoritative generation 已通过最小 readiness probe
   - `phase=mounted` 仅以这一层为发布条件
2. namespace UI readiness
   - project tmux namespace 已存在
   - authoritative session/window target 已可被 tmux 选择
   - 当前 UI contract 已应用
3. desired-agent acceptable mounted state
   - 显式 foreground start 需要的 agent 已达到可接受 mounted 状态
   - recovering agent 必须有明确 persisted reason 与 active reconcile ownership

等待规则固定为：

- `ccb ask`、`ping`、`pend`、`watch`、`queue` 等 daemon RPC caller 只等待 control-plane readiness
- 交互式 `ccb` 先等待 control-plane readiness，再等待 namespace UI readiness
- 前台 start 结果是否报告“configured agents ready”属于更高层 outcome，不得回灌为 backend mounted 的定义

### 6.5 启动预算策略

预算必须按层拆开，不能再复用一个通用 timeout 常量：

- `startup_transaction_timeout_s`
  - keeper-owned 冷启动事务的最大预算上限
  - 不是每次固定等待时长
  - 已 mounted 的热路径必须立即返回
  - 正在等待中的 caller 只要观察到事务成功或失败，也必须立即返回
- `startup_progress_stall_timeout_s`
  - 对 `startup_stage` / `last_progress_at` 的短超时
  - 用于提前识别卡死 bootstrap，而不是机械等满整体预算
- `rpc_probe_timeout_s`
  - 单次 socket connect / ping / config-check 的短超时
  - 应维持 fast-fail 语义，不得被提升到冷启动事务级别
- `foreground_attach_timeout_s`
  - 只服务交互式 `ccb` 的 namespace/UI attach 等待
  - 不得影响 `ask`、`ping` 等 control-plane caller

默认策略上，`startup_transaction_timeout_s` 应该是冷启动 ceiling，而不是 steady-state latency 目标。
实现上可以允许 20 到 30 秒的事务上限，但正常路径必须在 ready 后立刻返回，不能把该值表现成每次调用都要等待的固定延迟。

### 6.6 bootstrap 分层

`ccbd` bootstrap 必须拆成两层，而不是把全部重型初始化都压在 mounted 发布前：

- `bootstrap_core`
  - project identity / config identity
  - lifecycle / lease / ownership
  - socket server
  - 最小 control-plane RPC surface
- `bootstrap_runtime`
  - runtime supervision
  - namespace recovery
  - execution/completion tracker
  - restore/adopt 以及更重的 provider-facing bootstrap

原则：

- mounted 发布只依赖 `bootstrap_core` 完成后的 control-plane readiness
- 不属于最小 control-plane readiness 的重型工作，不得无界地阻塞 mounted 发布
- 冷启动 `ask` 允许在 backend mounted 后尽早提交，由 daemon supervision 异步完成后续 runtime 收敛

## 7. 显式停机时序

### 7.1 stop transaction

`ccb kill` 与 `ccb kill -f` 必须共享同一个 lifecycle transaction，只在强制程度上不同，不再是两套互斥世界观。

基础 stop transaction：

1. CLI 写入 `desired_state=stopped`
2. CLI 写入 shutdown intent
3. keeper 将 `phase` 推到 `stopping`
4. 若 socket 可连，优雅调用 `stop_all`
5. 若 socket 不可连但 pid 仍活着，keeper 直接执行本地终止
6. backend 仅清理属于自己 generation 的资源
7. keeper 观察到资源收口后，落到 `unmounted`

### 7.2 普通 kill 的强语义

显式 `ccb kill` 是用户管理动作。

因此：

- `socket_unreachable + heartbeat_fresh` 只能阻止自动 takeover
- 不能阻止显式 `kill`

也就是说：

- 自动恢复路径必须保守
- 显式停机路径必须更强

### 7.3 force kill

`ccb kill -f` 只在以下场景升级强度：

- 优雅 stop_all 超时
- runtime/helper group 无法随 authority 收口
- residue 明确阻塞停机闭环

但仍必须落到相同的 `phase=unmounted` 终态。

## 8. Generation Fence

### 8.1 backend generation

每次 keeper 启动新 `ccbd` 时，都必须分配新的 `generation + startup_id`。

### 8.2 失权规则

任何旧 generation 一旦失去 authority，只允许：

- 停止服务
- 退出

不允许：

- 再写 `unmounted`
- 再 unlink socket
- 再 destroy namespace
- 再 cleanup 新 generation 的 helper/runtime

### 8.3 heartbeat 规则

heartbeat 刷新必须带：

- `expected_generation`
- `expected_daemon_instance_id`

一旦不匹配，当前 generation 必须自退，而不是继续 serving。

## 9. Socket Ownership

### 9.1 目标

socket path 不能再通过 blind `unlink` + `bind` 方式竞争。

### 9.2 规则

1. socket cleanup 必须在 lifecycle lock 保护下进行
2. 只有当前 generation 持有 socket 清理权
3. bind 前不能因为 path 存在就直接删除
4. startup 只能清理已确认属于失效 generation 的 inode
5. shutdown 只能 unlink 自己 bind 的 inode
6. 旧 generation 不得删除新 generation 替换后的 socket path

### 9.3 目标结果

必须消除：

- `lease mounted` 但 `ccbd.sock` 已不可连
- 新实例启动时把仍属旧实例的 path 误删
- 旧实例退场时把新实例的 replacement socket 一并删掉

## 10. Keeper 观测与重启策略

### 10.1 authority 与 observation 分离

keeper 的重启决策必须主要依赖 authority，而不是单次观测噪声。

authority：

- `desired_state`
- `phase`
- `generation`
- `config_signature`

observation：

- pid 是否存活
- heartbeat 是否新鲜
- socket 是否可连
- live ping 是否超时

### 10.2 live ping 超时

live ping 或 config check 超时只应记为：

- `degraded_observation`

不能直接触发 restart。

### 10.3 允许 restart 的条件

keeper 只应在以下情况下进入新启动事务：

- `phase=unmounted && desired_state=running`
- `phase=failed && desired_state=running`
- 明确完成 stop transaction 后需要重配
- 当前 generation 已确认失权且完成收口

## 11. Provider Helper Ownership

### 11.1 基本原则

长期 provider helper/bridge 必须从“请求副产物”改成“slot-owned runtime component”。

不允许：

- 每次 ask 单独拉一个长期 bridge
- bridge 失去父进程后继续长期存在
- helper 只能通过 blind pid scan 才能发现

### 11.2 slot-scoped helper

一个 agent slot 在任一 runtime generation 下：

- 最多拥有一个长期 helper group
- helper group 必须落盘到 `helper.json`
- 后续 ask 复用该 helper，而不是重复派生新组

### 11.3 process group

长期 helper 必须以 process group 管理。

回收时以：

- `pgid`
- `runtime generation`
- `slot_key`

为主键，而不是零散 pid。

### 11.4 owner death

helper 必须具备 owner-death 收口能力。

推荐双保险：

- process-group 级 kill
- parent death / heartbeat channel 自退

目标是避免出现大批 `PPID=1` 的项目 owned bridge。

## 12. Orphan Sweeper

即使主生命周期闭环，也仍需要 project-scoped orphan sweeper 作为保险丝。

它只能做：

- 启动前读取 runtime/helper manifest
- 回收没有 current owner generation 的 helper group
- 清理与当前项目 authority 明确关联的 stale runtime residue

它不能做：

- 猜测全局 provider 进程
- 替代 lifecycle state machine
- 依赖 cwd 模糊匹配跨项目杀进程

## 13. Diagnostics

必须将当前单一的 “healthy/degraded” 视图拆成多维：

- `lifecycle_desired_state`
- `lifecycle_phase`
- `lifecycle_generation`
- `lifecycle_startup_id`
- `authority_health`
- `socket_health`
- `namespace_health`
- `runtime_health`
- `orphan_helper_group_count`
- `stale_runtime_group_count`
- `kill_blocked_reason`
- `last_failure_reason`

还必须增加 append-only lifecycle journal，记录：

- `start_requested`
- `starting_entered`
- `socket_bound`
- `mounted_entered`
- `stop_requested`
- `stopping_entered`
- `failed_entered`
- `unmounted_entered`
- `generation_superseded`
- `helper_group_spawned`
- `helper_group_reaped`

## 14. 实施阶段

### Phase 1: Project Lifecycle Authority

- 引入 `lifecycle.json`
- keeper 成为唯一 `ccbd` 启动者
- CLI 改为只写 intent 与等待 keeper-owned startup transaction
- 冷启动等待从通用 RPC timeout 中剥离

### Phase 2: Start/Stop Transaction Hardening

- 修正 `starting/mounted/stopping/failed`
- mounted 只在 ready 后发布
- 引入 readiness 分层与 path-specific timeout policy
- `ask` 冷启动只等待 control-plane readiness
- stop transaction 不再受 degraded socket 语义阻断
- socket ownership 增加 inode/generation fence

### Phase 3: Provider Helper Ownership

- helper 改为 slot-scoped process group
- 补齐 `helper.json`
- remount/kill 统一回收 helper group

### Phase 4: Diagnostics And Safety

- lifecycle journal
- orphan sweeper
- 观测降噪
- doctor / bundle 输出增强

## 15. 模块切分与职责迁移

### 15.1 keeper / lifecycle 侧

目标是把项目 phase 推进权集中到 keeper。

建议新增模块：

- `lib/ccbd/lifecycle_runtime/models.py`
- `lib/ccbd/lifecycle_runtime/store.py`
- `lib/ccbd/lifecycle_runtime/transaction.py`
- `lib/ccbd/lifecycle_runtime/journal.py`

职责：

- 定义 `desired_state`、`phase`、`generation`、`startup_id`
- 串行化 `start/stop/restart/fail` 事务
- 提供 keeper 唯一 phase 推进入口

现有模块调整：

- `lib/ccbd/keeper_runtime/loop.py`
  - 从“restart decision loop”升级为 lifecycle state machine driver
- `lib/cli/services/daemon.py`
  - 从“可直接启动 daemon”降级为 lifecycle client

### 15.2 backend 执行侧

目标是把 `ccbd` 收窄为“当前 generation 的执行者”。

建议新增或收口模块：

- `lib/ccbd/backend_runtime/startup.py`
- `lib/ccbd/backend_runtime/readiness.py`
- `lib/ccbd/backend_runtime/shutdown.py`

职责：

- 当前 generation 的 bind/listen/readiness
- 当前 generation 的 graceful shutdown
- generation-aware lease refresh

现有模块调整：

- `lib/ccbd/app_runtime/lifecycle.py`
  - 不再推进 project phase
  - 只负责执行本 generation 生命周期

### 15.3 socket ownership 侧

目标是把 socket inode ownership 做成显式 contract。

建议新增模块：

- `lib/ccbd/socket_runtime/ownership.py`
- `lib/ccbd/socket_runtime/bind.py`

职责：

- 记录当前 generation 绑定的 socket inode
- 启动前验证旧 inode 是否可清理
- 停机时只 unlink 自己的 inode

### 15.4 slot runtime / helper 侧

目标是把 provider helper 从“临时副产物”改为“slot-owned runtime resource”。

建议新增模块：

- `lib/provider_runtime/helper_groups.py`
- `lib/provider_runtime/helper_manifest.py`
- `lib/provider_runtime/helper_cleanup.py`

职责：

- 建立 helper process group
- 将 helper manifest 绑定到 slot runtime generation
- 在 remount/kill/stop transaction 中统一回收 helper group

现有 provider backend 模块：

- 仅保留 provider-specific start/facts/recover 能力
- 不再各自隐式持有长期 orphan helper 生命周期

## 16. 数据迁移与兼容切换

### 16.1 lifecycle.json 迁移

首次引入 `lifecycle.json` 时，必须支持从现有 `lease.json` 平滑迁移。

迁移规则：

- 若 `lifecycle.json` 缺失但 `lease.json` 存在：
  - 由 keeper 在持锁状态下生成初始 `lifecycle.json`
  - 若 lease 明确健康且 socket 可连，则迁移为 `phase=mounted`
  - 若 lease 为 `unmounted`，迁移为 `phase=unmounted`
  - 若 lease 与 socket/pid 事实矛盾，迁移为 `phase=failed`
- 若两者都缺失：
  - 初始为 `desired_state=stopped`、`phase=unmounted`

### 16.2 runtime/helper manifest 迁移

helper ownership 改造必须允许旧项目没有 `helper.json`。

迁移规则：

- 若旧 runtime 没有 helper manifest：
  - 启动时不把现存 bridge/pid 当 authority
  - 仅将其视为 evidence/residue
  - 新 generation 若需要 helper，则按新模式创建并落盘
- orphan sweeper 可回收与当前项目明确相关但无 manifest owner 的旧 helper residue

### 16.3 切换原则

切换必须遵守：

- 不依赖长期双轨
- 不允许 `CLI-direct-spawn` 与 `keeper-only-spawn` 长期共存
- 不允许旧 blind pid scan 与新 helper manifest cleanup 长期共存为同等主路径

短期兼容仅允许：

- 启动时读取旧 authority 并迁移
- 诊断中同时展示旧记录与新记录

补充要求：

- 兼容读取可暂时容忍旧 record 缺失 `runtime_generation`
- 新写入路径不得继续产出依赖 `binding_generation` 回退的 helper/runtime authority

## 17. 分阶段出口条件

### Phase 1 出口条件

- CLI 已不再直接启动 `ccbd`
- keeper 是同项目唯一 `ccbd` 启动者
- `lifecycle.json` 已成为 phase authority
- 同项目双终端并发 `ccb ask` 不会产生双 backend generation
- startup waiter 已不再依赖放大全局 `CcbdClient` timeout

### Phase 2 出口条件

- `mounted` 只在 readiness 后发布
- control-plane readiness 与 namespace UI readiness 已明确分层
- `startup_transaction_timeout_s` 已成为冷启动 ceiling 而非固定等待
- 普通 `ccb kill` 可处理 `socket_unreachable + heartbeat_fresh`
- 旧 generation 无法 unlink 新 generation socket
- 启动失败能够稳定落到 `phase=failed`

### Phase 3 出口条件

- slot runtime 有独立 `runtime_generation`
- 长期 bridge/helper 全部经 `helper.json` 管理
- `kill` / remount / `stop_all` 能整组回收 helper process group
- 不再出现新增的 project-owned `PPID=1` bridge 孤儿

### Phase 4 出口条件

- `doctor` 能输出 lifecycle/socket/runtime/helper 多维状态
- lifecycle journal 可追溯 start/stop/fail/restart
- orphan sweeper 可清理 stale helper residue
- 故障包足以解释 “谁有 authority、为何 failed、为何 kill 被阻断”

## 18. 测试计划

详细测试计划单独维护在：

- [docs/ccbd-lifecycle-test-plan.md](/home/bfly/yunwei/ccb_source/docs/ccbd-lifecycle-test-plan.md)

生命周期实现必须与该测试计划同步推进；若状态机、authority 边界、helper ownership 或阶段门禁发生变化，测试计划也必须在同一补丁中更新。

## 19. 运营与诊断要求

### 19.1 常态观测

项目级诊断至少要能回答：

- 当前项目是否有唯一 keeper
- 当前项目是否有唯一 mounted generation
- socket 是否 ready
- namespace 是否 healthy
- 当前有多少 helper groups
- 是否存在 stale/orphan helper residue

### 19.2 故障分类

未来诊断输出必须把故障至少区分为：

- `lifecycle_failed`
- `socket_not_ready`
- `authority_conflict`
- `shutdown_blocked_by_runtime`
- `helper_group_leak_detected`
- `orphan_helper_residue_detected`

### 19.3 性能目标

这套重构必须满足最低运行目标：

- 同项目启动/恢复不出现无界重启循环
- helper 数量对 agent 数量呈线性上界，而不是对 ask 次数线性增长
- `ccb kill` 在 degraded socket 状态下仍能于有界时间内收口

## 20. 验收矩阵

方案完成前，以下场景必须自动化并通过：

- 两个终端同时首次 `ccb ask`
- `ccbd` 在 `starting` 期间再次收到 `ccb ask`
- `socket_unreachable + heartbeat_fresh` 下普通 `ccb kill`
- `ccb kill` 与 keeper tick 并发
- config drift 导致的 orderly restart
- 旧 generation 失权后仍存活一小段时间
- slot remount 后旧 helper group 回收
- crash 后 orphan helper group sweep
- 连续 `start -> kill -> start -> ask`
- 多项目并行运行，各自独立 `ccbd`，互不接管

## 21. 非漂移规则

未来实现若改变以下内容，本文必须同步更新：

- keeper 是否仍是唯一 `ccbd` 启动者
- `mounted` 的严格含义
- 显式 `kill` 是否仍然强于自动 takeover 规则
- helper/bridge 是否仍由 slot runtime generation 拥有
- `lifecycle.json` / `lease.json` / `helper.json` 的 authority 边界

如果实现与本文冲突，应视为架构漂移，而不是实现细节。
