# CCBD 生命周期稳定性测试方案

## 1. 文档定位

这份文档是 `docs/ccbd-lifecycle-stability-plan.md` 的独立测试执行方案。

它不重新定义架构 authority，而是将生命周期稳定性设计转化为可执行测试计划、阶段门禁、长稳验证和 CI 接入要求。

若架构设计与本测试方案冲突，以以下文档为准：

- `docs/ccbd-startup-supervision-contract.md`
- `docs/ccbd-lifecycle-stability-plan.md`

## 2. 测试目标

测试计划必须证明两件事：

1. project lifecycle authority 是唯一且稳定的
2. provider helper ownership 是有界且可回收的

因此测试不能只验证“功能能跑通”，还必须验证：

- 同项目不存在双 keeper / 双 backend generation
- `mounted` 不会早于 readiness 发布
- 显式 `kill` 永远能收口到 `unmounted`
- helper/bridge 数量对 slot 数有上界，不会随 ask 次数无界增长
- 旧 generation 与 orphan residue 不会破坏当前 authority

## 3. 单元测试计划

### 3.1 核心覆盖

必须覆盖：

- lifecycle phase 转移
- keeper 持锁与并发等待
- readiness 前后 mounted 语义
- generation fence 拒绝旧实例写 authority
- helper manifest 序列化与回收策略

### 3.2 细分主题

建议新增或收口的测试主题：

- `lifecycle.json` 初始创建、读写、迁移、schema 校验
- `desired_state` 与 `phase` 的合法转移矩阵
- `startup_id` / `generation` 不匹配时的拒绝逻辑
- old generation 对 `lease`、socket cleanup、namespace cleanup 的写保护
- helper manifest 与 runtime generation 的一致性校验
- 普通 runtime state write 试图改写 authority 字段时必须被拒绝
- helper manifest writer 不得回退到 `binding_generation`
- orphan sweeper 的选择器只命中项目内 stale helper group

### 3.3 建议文件组织

- `test/test_v2_lifecycle_models.py`
- `test/test_v2_lifecycle_store.py`
- `test/test_v2_lifecycle_transactions.py`
- `test/test_v2_socket_ownership.py`
- `test/test_v2_helper_groups.py`

## 4. 集成测试计划

### 4.1 必测场景

必须覆盖：

- 同项目双终端并发 `ccb` / `ccb ask`
- `kill` 与 `start` / `ask` 并发
- lifecycle migration from old lease-only project
- config drift 导致的 orderly restart
- stop transaction 中 socket 不可连但 pid 活着

### 4.2 集成测试标准

集成测试应以“真实状态文件 + 受控进程假体 + 真实 tmux socket 或等价后端”为标准，不允许仅靠 monkeypatch 模拟所有关键时序。

### 4.3 重点用例

- 同项目两个 CLI 几乎同时发起 `ccb`，最终只产生一个 keeper 和一个 mounted generation
- 同项目两个 CLI 几乎同时发起 `ccb ask`，第二个请求必须等待已存在的 `starting` 事务
- `phase=starting` 时 child 启动失败，系统稳定落到 `phase=failed`
- `phase=mounted` 时 config 改动，keeper 通过 orderly restart 完成 generation 切换
- socket 不可连但 pid 仍存活时，普通 `ccb kill` 能经 keeper 收口，而不是被 degraded 拒绝
- `ccb kill` 与新的 `ccb ask` 并发时，新的 ask 只能等待停机结果，不得触发第二条启动链
- 从旧项目状态启动：
  - 只有 `lease.json`
  - 没有 `lifecycle.json`
  - 没有 `helper.json`
  都能进入确定性迁移路径

### 4.4 真实 CLI 生命周期 smoke 集

以下用例是固定的真实 `ccb` 黑盒生命周期基线，必须通过 `ccb` 入口拉起项目，而不是只调用后台 service：

- `test/test_v2_phase2_entrypoint.py::test_ccb_v2_project_lifecycle`
- `test/test_v2_phase2_entrypoint.py::test_ccb_ping_ccbd_recovers_from_stale_mount_and_bumps_generation`
- `test/test_v2_phase2_entrypoint.py::test_ccb_long_running_job_keeps_heartbeat_and_doctor_healthy`
- `test/test_v2_phase2_entrypoint.py::test_ccb_fake_provider_recovers_running_execution_after_ccbd_restart`
- `test/test_v2_ccbd_start_matrix.py::test_ccb_start_restarts_dead_daemon_on_subsequent_start`

统一执行入口：

- `python -m pytest -q -m ccb_lifecycle_smoke test/test_v2_phase2_entrypoint.py test/test_v2_ccbd_start_matrix.py`

CI 接入要求：

- GitHub macOS cross-platform workflow 必须运行这组 smoke，用于覆盖真实 tmux / namespace / socket / attach 时序
- Linux 运行同一 marker 作为基线对照，避免只在 macOS 上单点发现回归

### 4.5 建议文件组织

- `test/test_v2_project_lifecycle_integration.py`
- `test/test_v2_kill_lifecycle_integration.py`
- `test/test_v2_lifecycle_migration.py`

## 5. 黑盒压力测试计划

### 5.1 必测场景

必须覆盖：

- 多项目并行运行，各自 keeper/ccbd 独立
- 长时间 ask/pend/watch 循环下无 bridge 数量持续增长
- crash 注入后 orphan sweep 是否收口
- 单项目大量 agent 并发执行时 keeper 不发生重启风暴

### 5.2 观测重点

黑盒压力测试的重点不是精确业务回复，而是 lifecycle 与资源边界：

- `keeper` 数量
- `ccbd` generation 数量
- helper process group 数量
- socket inode 切换是否单调有界
- ask 次数增加时 helper 数是否稳定

### 5.3 压测脚本建议

- 多项目并发压测
  - 10 至 30 个项目并行 `ccb` / `ccb ask`
  - 验证互不接管、互不清理、互不复用 keeper
- 单项目高频 ask 压测
  - 1 个项目、多个 agent、循环 ask 1000 次以上
  - 观察 helper group 数量是否稳定
- kill/restart 抖动压测
  - 反复执行 `ccb ask`、`ccb kill`、`ccb`
  - 验证不会出现 stuck `starting` 或双 mounted generation

### 5.4 建议输出指标

- `keeper_count_per_project`
- `mounted_generation_count_per_project`
- `helper_group_count_per_agent`
- `orphan_helper_count_per_project`
- `lifecycle_phase_duration_seconds`

## 6. 故障注入测试计划

### 6.1 基本要求

必须显式构造：

- bind 前 socket 路径残留
- 旧 generation 延迟退出
- keeper config check timeout
- helper leader 死亡但子进程存活
- namespace destroy 与 helper cleanup 交叉发生

每个故障注入场景都必须定义：

- 注入点
- 预期 lifecycle phase
- 预期 cleanup 结果
- 不允许发生的副作用

### 6.2 注入矩阵

1. `starting` 前注入
- stale socket path 存在
- 旧 keeper state 残留
- 旧 `lease.json` 指向已死 pid

2. `starting` 中注入
- child 在 bind 前退出
- child 在 bind 后、readiness 前退出
- child readiness ping 超时

3. `mounted` 中注入
- socket accept 阻塞或超时
- backend heartbeat 正常但 socket 不可连
- config-check ping timeout

4. `stopping` 中注入
- stop_all 卡住
- provider helper group 无响应
- namespace destroy 成功但 helper group 仍存活

5. helper 侧注入
- helper leader 死亡，child 留存
- child 脱离 parent 成孤儿
- helper manifest 丢失但 pgid 仍存活

### 6.3 每个场景必须验证

- lifecycle 是否落到正确 phase
- 当前 authoritative generation 是否仍唯一
- 是否产生 stale helper / stale socket / stale lease residue

## 7. 阶段门禁

### 7.1 Phase 1 门禁

- 单元测试全部通过
- 同项目并发启动不会产生双 keeper / 双 backend generation
- `lifecycle.json` 迁移覆盖旧 lease-only 项目

### 7.2 Phase 2 门禁

- readiness gate 生效，`mounted` 不会早发
- 普通 `ccb kill` 覆盖 degraded/socket_unreachable 场景
- socket ownership 测试覆盖 inode fence

### 7.3 Phase 3 门禁

- helper manifest + process group cleanup 覆盖所有长期 helper backend
- ask 高频循环下 helper 数量稳定
- 无新增 project-owned `PPID=1` helper 泄漏
- helper ownership 写路径只依赖 canonical `runtime_generation`

### 7.4 Phase 4 门禁

- `doctor` / diagnostics 输出包含 lifecycle、socket、runtime、helper 指标
- orphan sweeper 可回收 stale helper residue
- fault bundle 足以解释最近一次 failed/stopping 卡点

## 8. 长稳与回归

### 8.1 soak tests

除一次性 CI 外，必须增加长稳测试与回归基线。

建议至少包含：

- 30 分钟单项目 soak
  - ask / pend / watch / kill / restart 循环
- 2 小时多项目 soak
  - 多个项目同时运行，观察 keeper 与 helper 数量是否稳定
- 崩溃恢复 soak
  - 周期性注入 backend crash，再观察是否出现 helper 累积

### 8.2 回归基线指标

- 单项目 keeper 最大数量恒为 1
- 单项目 mounted generation 最大数量恒为 1
- 单 agent 长期 helper group 最大数量恒为 1
- orphan helper 数在 crash 后可回落到 0 或明确受控上限
- `ccb kill` 的收口时间在有界阈值内

## 9. 手工验证清单

在自动化之外，仍需保留最小手工验证清单，用于发版前确认用户可见行为。

建议手工清单：

- 新项目首次 `ccb`
- 已有项目 `ccb` 恢复历史
- `ccb ask agentX` 正常提交与回复
- `ccb kill` 后当前项目不再保留 mounted backend
- `ccb kill -f` 可清理异常状态
- 多项目同时运行互不影响
- 观察系统进程，确认无持续增长的 provider helper/bridge

手工验证应记录：

- 项目路径
- phase 变化
- keeper pid / ccbd pid
- helper group 数量前后变化
- 是否出现 orphan residue

## 10. CI 与观测接入

### 10.1 CI 分组

CI 不应只执行功能性 pytest，还应输出关键生命周期指标。

建议接入：

- lifecycle 测试分组
- helper ownership 测试分组
- 压力测试 smoke 分组
- 故障注入 smoke 分组

### 10.2 失败时上传内容

CI 失败时应优先上传：

- `lifecycle.json`
- `lease.json`
- startup/shutdown report
- lifecycle journal
- helper manifests
- recent stderr/stdout logs
