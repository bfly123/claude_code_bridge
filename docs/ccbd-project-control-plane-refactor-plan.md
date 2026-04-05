# CCBD 项目控制面架构重构方案

## 1. 文档定位

这份文档是当前重构阶段的执行基线。

目标不是继续修补现有 `askd` / session / pane / registry 多头并存的实现，而是基于最新 `archi` 结果与当前闭环目标，重新定义项目控制面的最终形态、模块边界与分阶段改造计划。

这份文档优先级高于以下文档中与项目控制面直接冲突的旧表述：

- `docs/agent-first-v2-architecture.md`
- `docs/agent-first-v2-clean-core.md`
- `docs/current-project-structure.md`

与“项目专属 tmux namespace + `ccb`/`ccb open`/`ccb kill` 生命周期收敛”直接相关的详细实施方案，见：

- `docs/ccbd-project-namespace-lifecycle-plan.md`

若旧的 tmux/pane 细节表述与该文档冲突，以新文档为准。

本方案采用纯净 cutover 思路，不为以下目标付出复杂度：

- 旧命名兼容
- 多条启动路径长期共存
- 祖先目录/全局配置回退
- pane blind search
- registry 反推当前绑定
- provider session 作为主路由真相

## 2. 设计输入

### 2.1 用户目标

当前阶段的硬目标已经明确：

- 每个 `.ccb` 根目录只能启动唯一项目实例
- 每个 `.ccb` 根目录只能存在唯一绑定权威
- 一个项目下可以管理任意多 agent
- 配置、启动、运行、停止必须形成单一路径闭环
- 不做降级方案、临时方案、旧兼容方案

### 2.2 Archi 基线

`2026-04-02` 最新全量分析结果：

- overall: `50.33`
- governance: `36.49`
- structure: `64.16`

最高风险组件：

- `lib:askd` risk=`158.05`
- `lib:provider_execution` risk=`93.6`
- `lib:mail` risk=`76.25`

最高热点文件：

1. `lib/opencode_comm.py`
2. `lib/claude_comm.py`
3. `lib/terminal.py`
4. `lib/codex_comm.py`
5. `lib/laskd_registry.py`

### 2.3 Archi 结果的直接解释

这些结果对当前重构的含义非常明确：

1. 问题不是目录不统一，而是 authority 没收口。
2. 不能再把更多复杂度无脑塞进当前 `askd` 大组件，否则只会继续放大最高风险组件。
3. 控制面必须唯一，但实现上必须分层，不能做成单体泥球。
4. provider comm 与 terminal 层热点很高，说明新架构必须减少“从 CLI 穿透到 pane/session/log”的跨层逻辑。
5. `mail` 风险很高，但它不是当前项目控制面闭环的主路径，不应反向污染当前重构。

结论：

- 必须坚持单一控制面与单一权威
- 但不能继续维持“所有事情都在 askd 包里”的实现方式

## 3. 当前实现消化结果

### 3.1 已经做对的部分

当前实现里，以下方向是正确的，应保留：

- `.ccb` 已经是项目状态根
- `PathLayout(project_root)` 已经把大部分状态约束到 `.ccb/` 下
- 项目配置已经收敛到项目本地，不再依赖全局 `~/.ccb`
- workspace binding 已经能表达“子工作区绑定回项目根”
- mailbox / message / reply / job store 已经基本遵循单写者模型
- `askd` 现有 lease + socket + startup lock 已经具备“唯一实例”的基础能力

### 3.2 当前闭环为什么仍然不成立

当前架构的核心问题不是某个 bug，而是 authority 分裂：

1. 项目身份双轨并存
   - 新链路：`project.ids.compute_project_id(project_root)`
   - 旧链路：`project_id.compute_ccb_project_id(work_dir)`

2. 项目边界规则不一致
   - CLI 上下文已经偏向“当前目录或 bootstrap”
   - session 查找仍然会做 ancestor scan
   - 某些读取链路仍允许从当前目录、父目录、workspace binding、registry 多头猜测

3. 绑定真相不唯一
   - `.ccb/.<provider>-session`
   - `.ccb/agents/<agent>/runtime.json`
   - pane registry
   - pend/session path 回读链路

4. 启动和停止不是闭环
   - `ccb start` 仍由 CLI 编排 workspace、pane、binding，再回写 askd
   - `ccb kill` 仍依赖猜 pid、猜 tmux socket、猜 pane、猜 proc cwd

5. provider 侧仍有半独立 runtime/daemon 语义
   - 项目控制面没有完全收回 start/stop/bind/reconcile

### 3.3 对当前代码的结构判断

当前真正健康的部分不是启动链，而是单写者存储内核：

- `message_bureau`
- `mailbox_kernel`
- `jobs.store`
- `agents.store`

当前最不健康的部分是跨层读写链：

- CLI 直接编排 runtime
- provider session 文件参与 authority
- pane registry 参与路由
- resolution 层做多路猜测

## 4. 命名决策：`askd` 重命名为 `ccbd`

结论：应该改。

原因不是“名字好听”，而是当前组件语义已经不是 ask-only daemon，而是项目级控制面。继续叫 `askd` 会持续误导架构边界。

### 4.1 为什么 `ccbd` 更合适

- `ccb` 是项目级框架名
- 当前守护进程负责的不只是 ask，还包括启动、附着、绑定、恢复、状态、观测、停止
- 它的真实角色是 project control plane daemon
- 名字统一后，`.ccb` 根目录下的控制面语义更清晰

### 4.2 命名切换的目标范围

本方案中的目标命名：

- `askd` 组件重命名为 `ccbd`
- `askd.sock` 重命名为 `ccbd.sock`
- `.ccb/askd/` 重命名为 `.ccb/ccbd/`
- 用户可见文档、状态输出、错误信息统一使用 `ccbd`

保留说明：

- 当前代码层面仍存在 `askd` 包名和路径
- 本文档将其视为待切除历史命名，而不是最终目标命名

## 5. 目标架构

## 5.1 顶层原则

新的控制面必须同时满足以下约束：

- 一个 `.ccb` 根目录只有一个项目身份
- 一个 `.ccb` 根目录只有一个控制面实例
- 一个 agent 只有一份权威 runtime binding
- CLI 只能走单一路径进入控制面
- provider 只能提供事实，不能拥有项目级 authority
- pane 只能是 runtime 字段，不能是路由主键

## 5.2 目标闭环

最终闭环固定为：

```text
cwd
  -> project bootstrap
  -> project root / .ccb
  -> ccbd
  -> runtime supervisor
  -> provider adapter
  -> binding authority
  -> message/job/mailbox store
```

解释：

- `project bootstrap` 只负责解析项目根、创建 `.ccb`、准备配置
- `ccbd` 只负责控制面入口与协调
- `runtime supervisor` 负责 start/stop/reconcile
- `provider adapter` 只负责 provider-specific 事实提取与执行
- `binding authority` 是唯一 runtime truth
- 业务状态最终写入单写者存储

### 5.2.1 启动闭环

```text
ccb
  -> resolve/bootstrap project
  -> connect/start ccbd
  -> request start(agent set)
  -> ccbd calls runtime supervisor
  -> supervisor prepares workspace/runtime
  -> supervisor starts provider runtime
  -> supervisor writes runtime binding
  -> ccbd reports final state
```

关键规则：

- CLI 不再自己生成最终 binding
- CLI 不再自己决定 pane 是否有效
- CLI 不再自己回写 runtime.json

### 5.2.2 运行中读路径

```text
ccb ps/ping/pend/logs/watch
  -> ccbd RPC
  -> runtime authority / job store / mailbox store
  -> return structured result
```

关键规则：

- 不从 pane registry 反推
- 不从 provider session 文件反推
- 不做 ancestor session scan

### 5.2.3 停止闭环

```text
ccb kill
  -> ccbd shutdown/stop-all RPC
  -> runtime supervisor stops children
  -> supervisor clears bindings
  -> ccbd marks lease unmounted
  -> return final cleanup summary
```

关键规则：

- `kill` 由控制面统一执行
- CLI 不能再做盲目 pid 猜测作为主路径
- pane/socket/pid 清理必须基于 runtime authority 的已知子进程集合

## 5.3 唯一 authority 设计

### 5.3.1 项目身份

唯一合法项目身份：

- `project_root -> compute_project_id(project_root)`

必须删除：

- 基于 `work_dir` fallback 的 project id 计算
- 旧 `project_id.py` 作为运行时主身份来源

### 5.3.2 项目配置

唯一合法项目配置：

- `.ccb/config.yaml`

规则：

- 在当前目录执行 `ccb`
- 如果当前目录有 `.ccb`，直接使用
- 如果当前目录没有 `.ccb`，向上找最近祖先 `.ccb`
- 如果找到了祖先 `.ccb`，当前目录视为项目子目录
- 如果没找到祖先 `.ccb` 且当前目录不是项目子目录，自动创建 `.ccb/config.yaml`

禁止项：

- `~/.ccb/ccb.config`
- `.ccb/ccb.config` 作为最终契约
- 全局回退
- 根目录外 provider session 反推项目配置

### 5.3.3 运行时绑定

唯一权威 binding：

- `.ccb/agents/<agent>/runtime.json`

它必须记录至少以下字段：

| 字段 | 含义 |
| --- | --- |
| `agent_name` | agent 主身份 |
| `project_id` | 所属项目身份 |
| `provider` | provider 类型 |
| `workspace_path` | 当前 agent 工作目录 |
| `runtime_root` | provider runtime 根目录 |
| `runtime_pid` | 主 runtime pid |
| `terminal_backend` | `tmux` |
| `pane_id` | 当前 pane 标识 |
| `tmux_socket_name` | tmux socket 名 |
| `session_file` | provider session 文件路径 |
| `session_id` | provider session id |
| `lifecycle_state` | starting / idle / busy / degraded / stopped |
| `health` | 当前健康状态 |
| `binding_generation` | 本次绑定代号，避免旧数据回写覆盖 |
| `last_seen_at` | 最近一次 supervisor 观测时间 |
| `managed_by` | 固定为 `ccbd` |

说明：

- provider session 是事实来源之一，但不是 authority
- pane 只是 runtime 事实字段，不是主路由键
- 外部 attach 如果允许存在，也必须经过 ccbd 校验后写入这份 authority
- 原生 Windows 未来若引入 `psmux`，应通过独立的 backend implementation 维度表达，而不是重新把 legacy native backend 放回 authority 字段

## 5.4 控制面分层

`ccbd` 必须是唯一控制面入口，但不能是单体泥球。

建议目标分层如下：

### 5.4.1 `project bootstrap`

职责：

- 解析项目根
- 创建 `.ccb`
- 读写默认 `config.yaml`
- 生成 `ProjectContext`

非职责：

- 不启动 provider
- 不操作 pane
- 不写 runtime binding

### 5.4.2 `ccbd`

职责：

- RPC socket
- 生命周期入口
- 调用 supervisor / binding / stores
- 对 CLI 暴露统一控制面 API

非职责：

- 不直接实现 provider-specific 启动细节
- 不直接承担所有状态机分支

### 5.4.3 `runtime supervisor`

职责：

- start / stop / reconcile
- 子进程树管理
- pane 生命周期管理
- 恢复/探活

非职责：

- 不持有最终 authority
- 不对外暴露 CLI 协议

### 5.4.4 `binding authority`

职责：

- 唯一写 `runtime.json`
- 管理 binding generation
- 校验当前 binding 是否可提交

非职责：

- 不直接启动 provider

### 5.4.5 `provider adapters`

职责：

- provider-specific 启动参数
- session 信息提取
- provider-specific health probe
- completion / execution 细节

非职责：

- 不计算项目身份
- 不决定项目路由
- 不写项目级 authority

## 6. 目标状态布局

建议目标目录如下：

```text
.ccb/
  config.yaml
  ccbd/
    lease.json
    ccbd.sock
    state.json
    stdout.log
    stderr.log
    submissions.jsonl
    messages/
      messages.jsonl
    replies/
      replies.jsonl
    mailboxes/
    executions/
    snapshots/
    cursors/
    provider-health/
    restore-report.json
    tmux-cleanup-history.jsonl
  agents/
    <agent>/
      agent.json
      runtime.json
      restore.json
      jobs.jsonl
      events.jsonl
      provider-runtime/
        <provider>/
      logs/
  workspaces/
    <agent>/
```

含义：

- `.ccb/ccbd/` 是项目控制面域
- `.ccb/agents/<agent>/` 是 agent authority 域
- `.ccb/workspaces/` 是默认工作区物化域

## 7. 必须删除的旧路径

以下内容不应继续作为主架构的一部分：

- `project_id.py` 旧 project identity 链路
- `pane_registry_runtime/*` 作为路由依据
- `provider_sessions.files.find_project_session_file()` 的 parent scan 逻辑
- `askd/client_runtime/resolution.py` 的 registry fallback 与 daemon cwd fallback
- 根目录级 `.claude-session` / `.codex-session` 作为项目 authority
- CLI 本地编排 start/attach/kill 后再回写 authority 的模式
- provider runtime/daemon 作为独立项目控制面

## 8. 实施原则

### 8.1 纯 cutover

每一阶段都要遵守：

- 不加 compat 分支
- 不引入 feature flag 维持双轨
- 不保留“暂时两种方式都能用”

### 8.2 先收 authority，再拆热点

`archi` 告诉我们的重点不是“先修最热文件”，而是“先收拢 authority，避免继续给热点喂复杂度”。

因此顺序必须是：

1. 收控制面闭环
2. 切掉旧 resolution / registry / session authority
3. 再拆热点大文件

### 8.3 mail 不进入当前主路径

`lib:mail` 风险很高，但当前阶段不应把 mail 系统重新拉进项目控制面主链路。

当前策略：

- 保持解耦
- 不允许 mail 反向决定项目运行时 authority
- mail 的清理与重构单列到后续阶段

## 9. 架构重构计划表

| 阶段 | 目标 | 主要改动 | 必删内容 | 验收标准 |
| --- | --- | --- | --- | --- |
| P0 | 冻结新架构契约 | 确认 `askd -> ccbd`、`.ccb/config.yaml`、唯一 runtime authority、唯一启动/停止闭环 | 继续新增旧路径设计 | 文档成为唯一执行基线 |
| P1 | 项目解析与配置收口 | 重写 project bootstrap；固定当前目录/祖先 `.ccb`/本地初始化规则 | 全局 `~/.ccb`、旧 `ccb.config` 契约 | `ccb` 在根目录、子目录、无 `.ccb` 目录三种场景行为唯一且确定 |
| P2 | 项目身份收口 | 统一到 `compute_project_id(project_root)`；删除旧 `project_id.py` 主路径使用 | work_dir-based project id | 所有 runtime/job/ping/kill 都只输出一种 project id |
| P3 | `ccbd` 控制面落地 | `askd` 重命名为 `ccbd`；调整 socket/lease/state path | `askd` 旧命名留在主输出和主路径中 | 启动/日志/错误/状态输出统一使用 `ccbd` |
| P4 | binding authority 落地 | 统一由 `ccbd` 写 `.ccb/agents/<agent>/runtime.json` | provider session / registry 双重 authority | `ps/ping/pend/logs/kill` 只读 runtime authority 或 ccbd RPC |
| P5 | runtime supervisor 收口 | start/stop/reconcile 全部进 supervisor；CLI 变 thin client | CLI 本地 pane 编排和盲杀 | `ccb kill` 不再依赖 blind pid/pane scan |
| P6 | 读路径 cutover | 删除 registry routing、ancestor session scan、daemon cwd fallback | `pane_registry_runtime` 主路由、resolution fallback | 所有读路径只走 `ccbd` 或 runtime authority |
| P7 | provider 边界瘦身 | provider adapter 只保留 provider facts；不再写项目 authority | provider 自写 project/session authority | provider 新增/修改不再碰项目路由代码 |
| P8 | 热点文件拆分 | 拆 `opencode_comm`、`claude_comm`、`terminal`、`codex_comm` 等热点 | 新增跨层 if/else 堆叠 | hotspot 再次分析时不继续集中在跨层大文件 |

## 10. 阶段交付清单

### 10.1 P0-P2 交付物

- 新的 project bootstrap 规则
- `.ccb/config.yaml` 新契约
- 单一 project id 路径
- 旧 `project_id.py` 退出主链路

### 10.2 P3-P5 交付物

- `ccbd` 命名切换
- `runtime supervisor`
- `runtime authority store`
- `ccb start/kill/ps/ping/pend/logs` 统一走控制面

### 10.3 P6-P8 交付物

- 删除 registry 主路由
- 删除 session blind search
- provider adapter 彻底退到事实层
- 基于新 authority 边界拆热点文件

## 11. 详细执行包

这一节把阶段计划进一步压缩为可独立提交、可独立回归的执行包。

建议原则：

- 每个执行包都必须能单独通过测试
- 每个执行包都必须减少一种 authority 分裂
- 不允许“先堆新代码，最后一起删旧逻辑”

### 11.1 执行包 A：bootstrap 与配置契约收口

目标：

- 固定项目发现规则
- 固定 `.ccb/config.yaml` 新契约
- 结束 `ccb.config` 作为最终契约的状态

触达模块：

- `lib/project/resolver.py`
- `lib/project/discovery.py`
- `lib/cli/context.py`
- `lib/cli/phase2.py`
- `lib/agents/config_loader_runtime/*`

具体动作：

1. 把 `CONFIG_FILENAME` 从 `ccb.config` 改为 `config.yaml`
2. 重写默认配置模板与加载器
3. 明确三种入口语义
   - 当前目录已有 `.ccb`
   - 当前目录无 `.ccb` 但祖先有 `.ccb`
   - 当前目录与祖先都无 `.ccb`，则本地创建
4. 删掉对全局 `~/.ccb/ccb.config` 的任何依赖与文档表述

退出标准：

- 所有项目上下文都通过统一 bootstrap 规则建立
- 新项目初始化只生成 `.ccb/config.yaml`

### 11.2 执行包 B：项目身份收口

目标：

- 全项目只保留 `compute_project_id(project_root)`

触达模块：

- `lib/project/ids.py`
- `lib/project_id.py`
- `lib/pane_registry_runtime/*`
- `lib/pend_cli/session_paths.py`
- `lib/askd/client_runtime/resolution.py`
- provider session / binding 更新链

具体动作：

1. 盘点所有 `compute_ccb_project_id` 调用点
2. 区分真正需要的是：
   - project id
   - workspace scope id
   - provider session key
3. project id 全部切回 `project.ids.compute_project_id`
4. 只保留 worktree scope 的局部概念，不再用作项目 authority
5. 删除 `project_id.py` 的主流程依赖

退出标准：

- 项目级输出只剩一种 `project_id`
- 不再出现 `work_dir fallback -> project id` 逻辑

### 11.3 执行包 C：`askd -> ccbd` 命名切换

目标：

- 统一控制面命名

触达模块：

- `lib/askd/*`
- `lib/cli/services/daemon.py`
- `lib/storage/paths.py`
- `lib/cli/render.py`
- 黑盒命令输出与错误消息

具体动作：

1. 先切用户可见命名
   - 输出
   - 日志
   - socket path
   - lease path
2. 再切目录命名
   - `.ccb/askd/ -> .ccb/ccbd/`
3. 最后切代码包命名
   - `askd` 包迁移到 `ccbd`

说明：

- 这一步可以分两次提交
- 但完成阶段退出前，不允许主输出里继续混用 askd/ccbd 两套名称

退出标准：

- 用户可见路径和输出统一只出现 `ccbd`

### 11.4 执行包 D：runtime authority 落地

目标：

- `.ccb/agents/<agent>/runtime.json` 成为唯一 binding truth

触达模块：

- `lib/askd/services/runtime.py`
- `lib/agents/store.py`
- `lib/agents/models_runtime/runtime.py`
- `lib/cli/services/ps.py`
- `lib/cli/services/provider_binding.py`

具体动作：

1. 扩展 `AgentRuntime` 字段
2. 引入 binding generation
3. 定义 runtime authority writer
4. 所有读路径统一改成：
   - 先读 ccbd
   - 或读 authority store
5. `provider_binding` 降级为 provider facts adapter，而不是 authority reader

退出标准：

- `runtime.json` 足够支撑 `ps/ping/pend/logs/kill` 主路径

### 11.5 执行包 E：start 路径收口到 control plane

目标：

- CLI 不再本地编排 runtime 和最终 binding

触达模块：

- `lib/cli/services/start.py`
- `lib/launcher/*`
- `lib/askd/app.py` 或未来 `lib/ccbd/app.py`
- `lib/askd/handlers/*`

具体动作：

1. CLI 只做 context build 和 start RPC
2. workspace materialize / runtime launch / authority write 迁入 supervisor
3. 删除 CLI 本地 `attach` 作为最终 authority 的路径

退出标准：

- 从 `ccb` 到 provider runtime 的主链只经过 control plane

### 11.6 执行包 F：kill 路径收口到 control plane

目标：

- `kill` 停止依赖 blind pid/pane/tmux 猜测作为主路径

触达模块：

- `lib/cli/services/kill.py`
- `lib/cli/services/daemon.py`
- `lib/askd/services/*`
- `lib/launcher/maintenance/*`

具体动作：

1. `kill` 改为 `stop-all` RPC
2. supervisor 按 authority 记录停止 provider runtime
3. `-f` 只作为兜底强制清理路径保留
4. 把 blind scan 从主路径移除，降级为紧急恢复工具

退出标准：

- 正常 `ccb kill` 不再读取 pane registry 或盲扫 pid 才能成功

### 11.7 执行包 G：读路径 cutover

目标：

- `ps/ping/pend/logs/watch` 全部退出 registry/session blind search

触达模块：

- `lib/pane_registry_runtime/*`
- `lib/provider_sessions/files.py`
- `lib/askd/client_runtime/resolution.py`
- `lib/pend_cli/*`
- `lib/cli/services/ps.py`

具体动作：

1. 删除 ancestor session scan
2. 删除 registry 路由主路径
3. 把 `pend` 从 provider session 回推切到 authority / ccbd RPC
4. provider session 文件保留为 provider artifact，不再承担项目 routing

退出标准：

- 在删除 registry 路由后，主流程功能不受影响

### 11.8 执行包 H：热点文件拆分与后收尾

目标：

- 在 authority 收口后，再处理高复杂度热点

触达模块：

- `lib/opencode_comm.py`
- `lib/claude_comm.py`
- `lib/terminal.py`
- `lib/codex_comm.py`
- 相关 provider backend runtime 子模块

具体动作：

1. 把跨层分支从 giant file 下沉到 provider adapter / terminal runtime 子模块
2. 避免新的 control plane 再穿透到底层 pane/log/session 细节
3. 保证热点拆分不再引回旧 authority 路径

退出标准：

- 新一轮 `archi` 热点不再集中在跨层巨石上

## 12. 当前推荐实施顺序

当前最合理的实现顺序如下：

1. 先完成文档冻结和命名决策
2. 再做 bootstrap + config + identity 收口
3. 然后切 `askd -> ccbd`
4. 接着做 runtime authority + supervisor
5. 再切 start/kill/read 路径
6. 最后删除 registry/session 盲找，并处理热点大文件

不建议的顺序：

- 先修 kill
- 先补 pane registry
- 先做更多兼容 fallback
- 先重写 provider comm 巨石而不先收 authority

这些做法都会继续把旧架构延长，而不是结束它。

## 13. 代码改造映射

下表用于把当前仓库中的关键模块映射到本方案下的目标职责。

| 当前模块 | 当前问题 | 目标去向 |
| --- | --- | --- |
| `lib/project/resolver.py` | 仍带旧 bootstrap 语义残留 | 保留为 project bootstrap 主入口，按 `.ccb/config.yaml` 新契约重写 |
| `lib/project/ids.py` | 正确，但还没成为唯一身份来源 | 保留并升级为唯一 project id 模块 |
| `lib/project_id.py` | 旧 work_dir routing id | 彻底删除主路径使用，最终删除文件 |
| `lib/cli/context.py` | 仍承担 bootstrap_if_missing 分叉 | 保留 facade，内部改成纯 bootstrap/context build |
| `lib/cli/services/start.py` | CLI 直接编排 workspace/runtime/binding | 改成纯 RPC client，不再本地落 binding |
| `lib/cli/services/kill.py` | 依赖 blind pid/tmux/proc scan | 改成纯 `ccbd stop-all` client |
| `lib/cli/services/daemon.py` | 仍是 askd 视角且夹杂 shutdown fallback | 重构为 `ccbd` client/bootstrap helper |
| `lib/askd/app.py` | 当前组件过重 | 重命名到 `lib/ccbd/app.py`，只保留控制面入口与 service wiring |
| `lib/askd/services/runtime.py` | binding authority 与 provider reload 混杂 | 拆成 runtime authority + runtime supervisor 协调层 |
| `lib/askd/services/ownership.py` | 语义正确但命名旧 | 迁移为 `ccbd` lease/ownership 模块 |
| `lib/provider_sessions/files.py` | session 查找仍做 ancestor scan | 降级为 provider artifact I/O，不再承担项目路由 |
| `lib/askd/client_runtime/resolution.py` | registry fallback、daemon cwd fallback、多头猜测 | 删除主路径，读路径统一改成 ccbd/runtime authority |
| `lib/pane_registry_runtime/*` | pane registry 参与项目路由 | 降为调试/观察用途，随后退出主架构 |
| `lib/pend_cli/session_paths.py` | 仍会从 session/registry 回推绑定 | 改成只读 ccbd/runtime authority |
| `lib/launcher/*` 启动编排链 | 当前承担太多本地 runtime 启动细节 | 被 runtime supervisor 吸收；保留仅限 terminal/provider 启动辅助 |
| `lib/message_bureau/*` | 单写者模型健康 | 保留，继续作为项目控制面业务状态内核 |
| `lib/mailbox_kernel/*` | 单写者模型健康 | 保留，不让外层 fallback 反向污染 |
| `lib/jobs/store.py` | 结构稳定 | 保留，继续作为 job/event append store |

## 14. 测试策略与测试点矩阵

### 14.1 总体测试策略

测试必须和执行包绑定，而不是最后一次性补。

分层原则：

- 单元测试：验证单个契约变化
- 服务测试：验证单条控制面路径
- 黑盒测试：验证 CLI 视角闭环
- 系统测试：验证 tmux / provider 隔离 / pend 隔离等高风险路径

阶段门禁原则：

- A/B/C 阶段以单元测试 + 服务测试为主
- D/E/F/G 阶段必须补黑盒测试
- H 阶段以复杂度下降和回归完整为主

### 14.2 现有测试基线与用途

以下现有测试可直接作为改造基线：

| 测试文件 | 当前用途 | 对应执行包 |
| --- | --- | --- |
| `test/test_v2_project_resolver.py` | 项目解析、祖先 anchor、bootstrap 行为 | A |
| `test/test_v2_config_loader.py` | 项目配置加载与默认配置生成 | A |
| `test/test_v2_cli_context.py` | CLI 上下文与 bootstrap 行为 | A |
| `test/test_v2_phase2_entrypoint.py` | phase2 黑盒入口与 bootstrap 行为 | A/E |
| `test/test_v2_askd_mount_ownership.py` | lease、ownership、mounted/unmounted 语义 | C/F |
| `test/test_v2_askd_socket.py` | 控制面 socket 层 | C/E |
| `test/test_v2_askd_dispatcher.py` | 控制面 job/dispatcher 主路径 | E |
| `test/test_v2_cli_kill.py` | 旧 kill 行为基线 | F |
| `test/test_v2_kill_service.py` | kill 服务层基线 | F |
| `test/test_v2_ps_service.py` | ps 输出和 binding 读取 | D/G |
| `test/test_pend_cli.py` | provider pend/session 路径 | G |
| `test/test_ping_cli.py` | ping CLI 行为 | G |
| `test/test_session_file_override.py` | 显式 session file 行为 | G |
| `test/test_registry_project_id.py` | registry/project id 旧依赖基线 | B/G |
| `test/test_project_id.py` | 旧 project id 行为基线 | B |
| `test/test_v2_runtime_launch.py` | runtime 启动路径 | E |
| `test/test_v2_runtime_isolation.py` | 多 runtime 隔离 | D/E |
| `test/test_v2_workspace_manager.py` | workspace 规划与物化 | A/E |
| `test/test_v2_execution_service.py` | provider execution 主路径 | E/H |
| `test/test_v2_tmux_project_cleanup.py` | tmux 项目清理 | F |
| `test/test_v2_tmux_cleanup_history.py` | tmux cleanup history | F |
| `test/system_pend_isolation.sh` | pend 隔离系统级验证 | G |

### 14.3 每个执行包的测试点

#### A. bootstrap 与配置契约收口

保留并修改：

- `test/test_v2_project_resolver.py`
- `test/test_v2_config_loader.py`
- `test/test_v2_cli_context.py`
- `test/test_v2_phase2_entrypoint.py`

需要新增：

- `test/test_v2_project_resolver_config_yaml.py`
  - 验证 `.ccb/config.yaml` 新路径
  - 验证子目录向上解析
  - 验证无 `.ccb` 时本地初始化
- `test/test_v2_config_loader_yaml.py`
  - 验证 YAML/TOML 最终契约
  - 验证默认模板输出文件名和内容

重点断言：

- 不再生成 `.ccb/ccb.config`
- 不再读取 `~/.ccb/ccb.config`

#### B. 项目身份收口

保留并修改：

- `test/test_project_id.py`
- `test/test_registry_project_id.py`

需要新增：

- `test/test_v2_project_identity.py`
  - 验证所有主路径都只使用 `project_root`
  - 验证 workspace path 不会改变 project id
  - 验证不同 agent worktree 不影响 project id

重点断言：

- 删除 `project_id.py` 主依赖后主链路仍通过
- registry 不能再通过 work_dir 猜项目身份

#### C. `askd -> ccbd` 命名切换

保留并修改：

- `test/test_v2_askd_mount_ownership.py`
- `test/test_v2_askd_socket.py`

需要新增：

- `test/test_v2_ccbd_mount_ownership.py`
- `test/test_v2_ccbd_socket.py`

重点断言：

- 路径变为 `.ccb/ccbd/*`
- 输出文案只出现 `ccbd`

说明：

- 这一阶段允许先保留旧测试文件名作为过渡基线
- 但阶段完成前，测试名与断言内容都应完成命名切换

#### D. runtime authority 落地

保留并修改：

- `test/test_v2_ps_service.py`
- `test/test_v2_runtime_isolation.py`

需要新增：

- `test/test_v2_runtime_authority_store.py`
  - 验证 `runtime.json` 字段完整性
  - 验证 generation 更新语义
  - 验证 authority 只能单点写入
- `test/test_v2_runtime_binding_authority.py`
  - 验证 provider facts 更新后 authority 正确刷新

重点断言：

- `ps/ping/pend/logs` 能只依赖 runtime authority 工作

#### E. start 路径收口到 control plane

保留并修改：

- `test/test_v2_phase2_entrypoint.py`
- `test/test_v2_runtime_launch.py`
- `test/test_v2_execution_service.py`
- `test/test_v2_workspace_manager.py`

需要新增：

- `test/test_v2_ccbd_start_flow.py`
  - 验证 `ccb -> ccbd -> supervisor -> runtime authority`
- `test/test_v2_cli_start_thin_client.py`
  - 验证 CLI 不再本地写 binding

重点断言：

- start 主链不再从 CLI 直接回写 runtime authority

#### F. kill 路径收口到 control plane

保留并修改：

- `test/test_v2_cli_kill.py`
- `test/test_v2_kill_service.py`
- `test/test_v2_tmux_project_cleanup.py`
- `test/test_v2_tmux_cleanup_history.py`

需要新增：

- `test/test_v2_ccbd_stop_all.py`
  - 验证 control plane 统一 stop-all
- `test/test_v2_kill_without_blind_scan.py`
  - 验证在不依赖 pane registry 的条件下 kill 正常工作

重点断言：

- 正常 kill 不再以 blind pid/pane scan 为主路径

#### G. 读路径 cutover

保留并修改：

- `test/test_pend_cli.py`
- `test/test_ping_cli.py`
- `test/test_session_file_override.py`
- `test/system_pend_isolation.sh`

需要新增：

- `test/test_v2_pend_reads_runtime_authority.py`
- `test/test_v2_ps_without_registry.py`
- `test/test_v2_ping_without_session_scan.py`

重点断言：

- 删掉 registry routing 后功能仍成立
- 删掉 ancestor session scan 后功能仍成立

#### H. 热点文件拆分

保留并修改：

- `test/test_v2_execution_service.py`
- `test/test_terminal_runtime_*`
- provider backend 相关测试

需要新增：

- 按 provider/backend 子模块拆分后的精细单测

重点断言：

- 复杂度下降不以恢复旧 blind search 为代价

### 14.4 推荐回归命令

#### A-B 阶段

```bash
pytest -q \
  test/test_v2_project_resolver.py \
  test/test_v2_config_loader.py \
  test/test_v2_cli_context.py \
  test/test_v2_phase2_entrypoint.py
```

#### C-F 阶段

```bash
pytest -q \
  test/test_v2_askd_mount_ownership.py \
  test/test_v2_askd_socket.py \
  test/test_v2_askd_dispatcher.py \
  test/test_v2_runtime_launch.py \
  test/test_v2_runtime_isolation.py \
  test/test_v2_cli_kill.py \
  test/test_v2_kill_service.py \
  test/test_v2_ps_service.py
```

#### G-H 阶段

```bash
pytest -q \
  test/test_pend_cli.py \
  test/test_ping_cli.py \
  test/test_session_file_override.py \
  test/test_v2_execution_service.py \
  test/test_v2_tmux_project_cleanup.py
```

系统级补充：

```bash
bash test/system_pend_isolation.sh
```

### 14.5 阶段完成门禁

每个执行包完成后至少满足：

1. 本包涉及的旧 authority 路径已切断
2. 本包对应测试全部通过
3. 黑盒命令输出没有混用新旧术语
4. 未引入新的 fallback

## 15. 验收测试清单

重构过程中，验收不应只看“能不能启动”，而要验证 authority 是否真正闭环。

### 13.1 项目解析验收

- 在项目根执行 `ccb`，存在 `.ccb/config.yaml` 时直接启动
- 在项目子目录执行 `ccb`，正确绑定到最近祖先 `.ccb`
- 在无 `.ccb` 的普通目录执行 `ccb`，自动创建 `.ccb/config.yaml`
- 不再从全局目录或根目录外 session 文件推导项目

### 13.2 唯一实例验收

- 同一 `.ccb` 根并发执行两次 `ccb`，只能存在一个 `ccbd`
- `lease.json + ccbd.sock` 状态一致
- `ccbd kill` 后 lease 状态明确变为 unmounted

### 13.3 唯一绑定验收

- 启动单 agent 后，`runtime.json` 能完整表达当前 binding
- 启动多 agent 后，每个 agent 只有一份 binding authority
- 删除 provider session 文件后，`ps/ping/pend` 仍能基于 authority 返回状态
- pane id 改变时，只允许 supervisor 更新 `runtime.json`

### 13.4 停止闭环验收

- `ccb kill` 不依赖 blind pane scan 仍可完成清理
- `ccb kill -f` 只作为补充强制路径，不作为正常主路径
- kill 后不会残留“lease 已挂载但 socket 不通”的中间脏状态

### 13.5 读路径验收

- `ps`
- `ping`
- `pend`
- `logs`
- `watch`

这些命令都必须在不读取 registry 路由的前提下工作。

### 13.6 架构验收

- 删除 `project_id.py` 主路径依赖后，主流程仍完整
- 删除 `pane_registry_runtime` 主路径依赖后，主流程仍完整
- 删除 ancestor session scan 后，主流程仍完整
- CLI 不再本地写最终 binding

## 16. 结论

当前最重要的决定不是“修哪个 bug”，而是确认控制面的唯一 authority 边界。

最终结论如下：

- `askd` 应重命名为 `ccbd`
- `ccbd` 是唯一项目控制面入口
- `.ccb/agents/<agent>/runtime.json` 是唯一运行时绑定权威
- `.ccb/config.yaml` 是唯一项目配置契约
- CLI 必须变成 thin client
- pane、registry、provider session 都必须从主 authority 退位

只有这样，`一个 .ccb 根目录只能启动唯一 ccb、唯一绑定、管理多 agent` 才不是口号，而是结构上成立的系统事实。
