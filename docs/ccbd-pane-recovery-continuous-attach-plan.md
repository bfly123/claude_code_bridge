# CCBD Pane 恢复与前台连续性详细方案

## 1. 文档定位

这份文档是 `ccbd` 启动/监督契约在 “pane 死亡恢复” 场景下的详细实施方案，目标是解决当前的核心结构问题：

- 杀死单个 pane 会导致整个 `ccb` 前台退出
- daemon 已有恢复能力，但恢复层级选择过重
- `.ccb/ccb.config` 的 canonical layout 与前台 attach 连续性被错误耦合

它补充并细化以下文档：

- `docs/ccbd-startup-supervision-contract.md`
- `docs/ccb-config-layout-contract.md`
- `docs/ccbd-project-namespace-lifecycle-plan.md`

若上述文档与本文在 pane recovery 的实现层级上有冲突，以本文为实现细化依据；若 contract 本身需要改变，应同步回写到 contract 文档。

## 2. 当前问题的精确定义

### 2.1 用户可见症状

当前在 `ccb` 已打开的前台里杀死一个 agent pane，常见表现是：

- 当前 `ccb` 前台直接退出
- 看起来像“没有自动恢复”
- 再次执行 `ccb` 后项目可能重新拉起，但原 attach 已经断开

### 2.2 当前实际发生的链路

当前代码不是完全没有恢复，而是恢复路径过重：

1. health monitor 把 runtime 标成 `pane-dead` / `pane-missing`
2. supervision 发现该 runtime 属于项目专属 tmux socket
3. recovery 优先进入 project namespace reflow
4. `remount_project_from_policy()` 以 `recreate_namespace=True` 启动整项目恢复
5. namespace recreate 当前通过 `kill-server` 实现
6. 当前前台 `ccb` 只是一次 `tmux attach-session`
7. tmux server 被杀后，attach 立即退出

因此，当前问题不是“后台完全不会恢复”，而是：

- 单 pane 故障被升级成 whole-namespace 故障
- whole-namespace 恢复又通过 `kill-server` 实现
- 前台 attach 没有机会保持连续

### 2.3 根因归类

根因是恢复层级设计错误，不是单点 bug。

当前系统把两件事绑定到了一条动作里：

- 恢复 pane 到 `.ccb/ccb.config` 定义的 canonical 布局位置
- 维持前台 attach 连续性

而当前实现用 “销毁整个 tmux server 并重建” 来达成前者，直接破坏后者。

## 3. 设计目标

本方案固定以下目标：

1. 杀死单个 pane 时，当前前台 `ccb` 不退出
2. pane 恢复后优先回到原 logical slot，而不是漂移到任意位置
3. `.ccb/ccb.config` 仍然是布局 authority
4. `ccbd` 仍然是唯一恢复 authority
5. `ccb kill` 仍然是唯一允许销毁整个项目 tmux server 的正常入口

## 4. 非目标

以下内容不在本文范围内：

- provider prompt/protocol 细节
- mailbox / ask / reply 语义
- Windows `psmux` 适配实现
- provider-specific completion 抽取算法

## 5. 最终设计结论

### 5.1 恢复必须分层

恢复必须分成四层，且只能逐级升级：

1. `slot/pane recovery`
2. `workspace window reflow`
3. `project session remount`
4. `backend/server remount`

核心原则：

- 单 pane 死亡默认只允许停留在第 1 层或第 2 层
- 不允许把单 pane 恢复直接实现成第 4 层
- `cmd` 不是 agent runtime，但它同样是一个必须持续守护的 project slot；它的恢复层级必须复用同一套 namespace-level recovery 规则
- 对 `cmd` 而言，第一优先级不是 whole-workspace reflow，而是当前 workspace 内的本地 slot replacement；只有本地补位失败时才升级到 workspace reflow

### 5.2 tmux 资源要重新分层

每个 `.ccb` 项目采用以下 tmux 拓扑：

```text
project .ccb
  -> one ccbd backend
  -> one project tmux server/socket
  -> one long-lived tmux session
      -> one hidden control window (__ccb_ctl)
      -> one visible workspace window (ccb)
          -> cmd / agent1 / agent2 / ...
```

这意味着：

- `server/socket` 是项目级基础设施
- `session` 是前台 attach 的长期锚点
- `workspace window` 承载可见布局
- `pane` 只是 workspace 的叶子资源

### 5.3 当前 attach 必须锚到 session，而不是具体 pane/window

`ccb` 前台 attach 阶段的连续性必须建立在：

- session 不消失
- attach 不依赖某个具体 pane id
- workspace window 可以被替换，但 session 必须还活着

因此：

- 普通 pane recovery 禁止 `kill-server`
- workspace reflow 也禁止销毁整个 session

## 6. Authority 模型调整

### 6.1 新的 authority 层级

对于 pane recovery，authority 固定如下：

1. `.ccb/ccb.config`
2. `.ccb/ccbd/lease.json`
3. `.ccb/ccbd/project-namespace-state.json`
4. `.ccb/agents/<agent>/runtime.json`

其中：

- `slot_key` 是 authority
- `pane_id` 是 evidence
- `window_id` / `workspace_epoch` 是 recoverable authority

### 6.2 新增状态字段

建议新增或强化以下状态：

`project namespace state`

- `tmux_socket_path`
- `tmux_session_name`
- `namespace_epoch`
- `control_window_name`
- `control_window_id`
- `workspace_window_name`
- `workspace_window_id`
- `workspace_epoch`
- `layout_signature`
- `ui_attachable`

`agent runtime`

- `slot_key`
- `workspace_epoch`
- `window_id`
- `pane_id`
- `active_pane_id`
- `pane_state`
- `reconcile_state`

语义要求：

- `namespace_epoch` 只在 session 级重建时变化
- `workspace_epoch` 只在 workspace window 重建时变化
- `slot_key` 永远对应 `.ccb/ccb.config` 的逻辑叶子
- `pane_id` 改变不等于 agent identity 改变

## 7. 恢复状态机

### 7.1 恢复层级

对单个 desired runtime 的恢复顺序固定为：

1. 读取 runtime authority
2. 读取 provider session 与 tmux pane facts
3. 尝试 local pane respawn
4. 尝试 slot-local replacement
5. 如仍失败，尝试 workspace window reflow
6. 仅当 session/server 本身损坏时，才进入 full remount

### 7.2 Local Pane Respawn

适用条件：

- 原 `pane_id` target 仍然存在
- tmux ownership 仍归属本项目 slot
- provider `start_cmd` 明确可重放

动作：

- `respawn-pane -k -t <pane_id>`
- 保持原 pane 位置
- 更新 runtime facts

结果：

- 前台不掉
- 布局不变
- 这是首选恢复路径

### 7.3 Slot-Local Replacement

适用条件：

- 原 pane target 已经不存在
- 但 session 和 workspace window 仍然健康
- 当前 slot 可在现有 workspace 内重新分配 pane

动作：

- 在当前 workspace window 中创建 replacement pane
- 将其投影回原 `slot_key`
- 更新 pane identity / runtime authority
- 必要时按 slot 做一次局部布局修正

当前实现约束：

- slot-local replacement 的创建锚点必须是当前 authoritative workspace window 的 root pane
- 这一步负责把 replacement 拉回正确 project namespace 和正确 `slot_key`
- 这一步不承诺单靠局部 split 就完全恢复 canonical geometry
- canonical 几何恢复仍属于下一层 `workspace window reflow`
- 因此，当 replacement 已成功且当前没有 `BUSY` 冲突时，daemon 应立即继续执行 `workspace window reflow`，把 pane 拉回 canonical 位置

结果：

- 前台仍不掉
- workspace 不必整体重建

### 7.4 Workspace Window Reflow

适用条件：

- local respawn 和 slot replacement 都失败
- session 仍然健康
- 需要恢复 canonical layout

动作：

1. 保留当前 session 与 hidden control window
2. 在同一 session 中创建新的 workspace window
3. 根据 `.ccb/ccb.config` 完整 materialize 新布局
4. 为每个 slot 分配新 pane 并写回 authority
5. 将 client 切换到新 workspace window
6. 销毁旧 workspace window
7. `workspace_epoch += 1`

结果：

- 布局被完全恢复
- 前台 attach 仍留在同一 session 中
- 不允许使用 `kill-server`

### 7.5 Full Remount

只在以下场景允许：

- project socket/server 不可用
- session 消失
- namespace state 与实际 tmux server 严重不一致
- `ccb kill` / 显式 destructive reset

动作：

- 停止 backend 或完全重建 namespace

限制：

- 这不是普通 pane recovery 路径
- 不允许由单 pane 死亡直接触发

## 8. Hidden Control Window 设计

### 8.1 目的

引入 `__ccb_ctl` 的原因是为了解耦：

- session 连续性
- visible workspace 重建

如果没有 control window，workspace 是 session 唯一可见锚点；一旦 workspace 被杀，当前 attach 可能直接退出或跳到不可控状态。

### 8.2 规则

- control window 默认隐藏，不承载用户工作
- control window 只运行静默占位进程
- session 至少始终保留一个 control window
- workspace window 可被替换、重建、切换

### 8.3 foreground attach 语义

`ccb` 的 foreground attach 逻辑固定为：

1. attach 到 session
2. select 到当前 `workspace_window_name`
3. 若 workspace 正在 reflow，可短暂落在 control window，再切回新 workspace

补充时序规则：

- `ui_attachable=true` 代表 namespace authority 已经成立，但 tmux session/window target 在不同平台上可能存在短暂可见性延迟
- foreground attach 必须做有界等待，直到：
  - authoritative session 可 `has-session`
  - authoritative workspace window 可 `select-window`
- 若超过有界等待仍不可见，才允许把该次 foreground attach 判为失败

这样可以保证：

- attach 对 workspace 重建不敏感
- session 不丢，前台不掉

## 9. 模块与函数改造方案

### 9.1 必须拆分的恢复 API

当前错误在于一个 `remount_project_from_policy()` 同时承担：

- pane recovery
- namespace recreate
- full remount

必须拆成三条显式路径：

- `recover_slot_from_policy(agent_name, reason)`
- `reflow_workspace_from_policy(reason)`
- `remount_backend_from_policy(reason)`

约束：

- `pane_recovery:*` 只允许前两条
- `backend_lost:*` 才允许第三条

### 9.2 建议新增模块

建议新增：

- `lib/ccbd/services/project_namespace_runtime/reflow.py`
- `lib/ccbd/services/project_namespace_runtime/workspace.py`
- `lib/ccbd/services/project_namespace_runtime/slot_assignment.py`

职责：

- `reflow.py`
  - session 内 workspace 替换
  - old/new workspace 切换
  - workspace epoch 管理
- `workspace.py`
  - control window / workspace window 的创建、查找、销毁
- `slot_assignment.py`
  - `slot_key -> pane_id/window_id` 映射
  - replacement pane 分配

### 9.3 现有模块的改造重点

`lib/ccbd/supervision/loop_runtime.py`

- 将 `pane-dead` 的默认恢复从 namespace reflow 降级为 local recovery first
- `should_reflow_project_namespace()` 不再作为首选路径

`lib/ccbd/supervision/recovery_transitions.py`

- `attempt_recovery_action()` 改为：
  1. local recover
  2. slot replace
  3. workspace reflow
  4. full remount

`lib/ccbd/app_runtime/policy.py`

- 拆分 `remount_project_from_policy()`
- 让 policy 层显式表达恢复等级

`lib/ccbd/services/project_namespace_runtime/ensure_state.py`

- `force_recreate_namespace()` 不再对 pane recovery 使用
- 删除 pane recovery -> `kill_server()` 的耦合

`lib/ccbd/services/project_namespace_runtime/backend.py`

- 新增 window 级操作封装
- 禁止把 `kill_server()` 当作普通恢复工具

`lib/cli/services/start_foreground.py`

- attach 后显式 select 当前 workspace window
- 对 workspace epoch 切换保持兼容

`lib/cli/services/runtime_launch_runtime/tmux_panes.py`

- 当前 “assigned pane + respawn / fallback detached pane” 模型要改成 slot-aware
- detached fallback 不应再作为项目 workspace 的常规恢复手段

## 10. 迁移步骤

### 阶段 1：先止血

目标：

- 禁止单 pane recovery 使用 `kill-server`

动作：

- 拆分 policy API
- 调整 supervision recovery 分级
- 将 pane recovery 首选路径改为 `ensure_pane()` / respawn

完成标准：

- 杀死单个 pane 不再导致整个 `ccb` 前台退出

### 阶段 2：引入 session 内 workspace reflow

目标：

- 在不销毁 session 的前提下恢复 canonical layout

动作：

- 增加 control window
- 增加 workspace epoch
- 实现 workspace window 替换

完成标准：

- pane 无法原位 respawn 时，仍可在同一 session 内完整恢复布局

### 阶段 3：收紧 authority

目标：

- 让 slot identity 完整进入 authority

动作：

- runtime.json 回写 `slot_key/window_id/workspace_epoch`
- namespace state 回写 workspace 信息

完成标准：

- pane id 变化不再影响 agent identity

### 阶段 4：前台 attach 优化

目标：

- `ccb` foreground attach 对 workspace reflow 透明

动作：

- attach 后 select 当前 workspace
- 可选增加 epoch-aware 的前台自恢复逻辑

完成标准：

- workspace window 替换时前台仍保持同一 session

## 11. 自动化测试矩阵

至少新增或重写以下测试：

### 11.1 Pane Recovery

- `kill-pane agent1` 后，当前 attach 不退出
- 原 pane target 仍存在时走 `respawn-pane`
- 原 pane target 不存在时走 slot replacement
- 恢复后 agent 回到原 `slot_key`

### 11.2 Workspace Reflow

- 单 pane 无法局部恢复时，workspace window 被替换
- reflow 后 session 不变
- reflow 后 workspace epoch 递增
- reflow 后前台仍附着在同一 session

### 11.3 Busy 隔离

- 其他 agent `BUSY` 时不触发破坏性 workspace reflow
- 但 local respawn 仍允许执行

### 11.4 Kill 语义

- `ccb kill` 仍销毁 control window + workspace window + tmux server
- kill 后 lease 为 `unmounted`

## 12. 验收标准

本方案落地后，必须满足：

1. 杀死任意 agent pane，当前前台 `ccb` 不退出
2. 杀死 `cmd` pane，前台仍在同一 session 中
3. 恢复后的 pane 回到 `.ccb/ccb.config` 的原 logical slot
4. 只有 `ccb kill` 或 backend 严重损坏才会销毁 tmux server
5. 单 pane 故障不会再触发 `kill-server`

## 13. 实施优先级

最高优先级：

1. recovery 分级改造
2. 禁止 pane recovery 走 `kill-server`
3. 引入 workspace-level reflow

次优先级：

4. hidden control window
5. workspace epoch / slot authority 收紧
6. attach 透明切换优化

## 14. 最终一句话原则

`pane recovery` 只能恢复 pane / slot / workspace，不能默认恢复成 “摧毁整个项目 tmux server 再重建”。
