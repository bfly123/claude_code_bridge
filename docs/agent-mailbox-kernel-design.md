# Agent Mailbox Kernel 详细方案

## 1. 文档目标

这份文档定义下一代 CCB 通信内核的目标形态：

- 以 **agent-first** 为公开接口
- 以 **邮箱系统** 为核心抽象
- 以 **单接收串行** 为硬约束
- 以 **provider/backend 事实层** 与 **信息管理局策略层** 的强隔离为结构原则
- 在保留当前 agent runtime 世界模型的前提下，允许对现有 askd 上层做实质性重构

这不是“给旧 dispatcher 再加几个状态”的补丁方案，而是一个新的内核蓝图。

---

## 2. 为什么要做成邮箱系统

当前 askd 更接近“任务执行框架”：

- 有 job
- 有状态流转
- 有 provider execution
- 有 completion tracker

但它还不是一个成熟的 agent 通信内核，因为它缺少以下能力：

- 逻辑消息和执行 attempt 的分离
- 返回结果统一回流为入站事件
- 每个 agent 串行消费入站消息的强约束
- 广播后的 fan-in / quorum / wait-all
- retry / resubmit / dead-letter / lineage
- 基于 runtime 健康和 provider 事实的统一恢复策略

专业邮箱系统的价值不是“模仿 IMAP/SMTP”，而是引入以下强模型：

- **出站和入站分离**
- **入站消费串行**
- **回复也是入站事件**
- **投递不等于消费**
- **每次失败重试都有谱系**

---

## 3. 这不是普通邮箱系统

### 3.1 普通邮箱系统的核心假设

- 收件人是人
- 邮件投递后就算送达
- 回复只是另一封邮件
- 收件箱主要是信息存储，不是执行入口

### 3.2 当前系统的核心假设

- 收件人是 agent，不是人
- inbox 里的对象不是普通消息，而是 **可执行入站事件**
- reply 不是附属品，而是会影响后续行为的 **新入站事件**
- 收件人存在 runtime / workspace / provider backend
- 投递成功不代表处理完成，只有 **agent 开始消费并完成状态流转** 才算真正进入处理

因此这套系统应该定义为：

> 一个与 agent runtime 深度耦合的邮箱式通信内核，而不是通用邮件系统。

---

## 4. 与当前 Agent 系统的兼容边界

允许完全重构，不代表推翻当前 agent 世界模型。

### 4.1 必须保留的稳定概念

- `agent_name` 仍然是公开目标标识
- `.ccb/ccb.config` 仍然是 agent 配置真相来源
- `provider` 仍然只是 `AgentSpec` 的属性，不再是公开 target
- `workspace_path` / `runtime_ref` / `session_ref` 仍然是 agent runtime 的关键上下文
- 每个 agent 的 `queue_policy` 语义仍然有效，尤其是 `serial-per-agent`

### 4.2 必须抛弃的旧中心模型

- 以 `job` 作为整个系统主语
- 把 reply 当作 completion hook 的旁路回调
- 让 provider/backend 参与公开路由语义
- 在 CLI 层硬编码异步/阻塞行为差异
- 把 `pend` 当成主链路结果获取方式

### 4.3 兼容性的正确目标

要兼容的是 **当前 agent 系统语义**，不是旧内部实现结构。

兼容目标是：

- 用户仍然向 agent 说话
- agent 仍然有 workspace / runtime / provider backend
- sender 推断仍然有意义
- watcher / logs / doctor / queue 等运维面仍然围绕 agent 展开

---

## 5. 硬不变量

后续任何实现都不能违反以下约束。

### 5.1 每个 agent 的入站事件必须串行消费

```text
Per-Agent Inbound Serialization Invariant

For any agent, all inbound events are serialized through one inbox queue.
An agent may emit many outbound messages without blocking, but it may consume
at most one inbound event at a time.
Replies and notifications share the same inbound delivery lane as new tasks.
```

### 5.2 发送与接收必须分离

- agent 可以连续快速发出很多出站消息
- 发送不会占用它的 inbound lease
- 只有消费入站事件才会占用接收槽位

### 5.3 返回信息不能直达

- reply 不能直接打进 caller pane
- 必须先落成 `ReplyRecord`
- 再生成 `InboundEvent(type=task_reply)`
- 再进入 caller 的 inbox 排队

### 5.4 provider 层只报告事实，不做策略

provider/backend 层只负责：

- 启动
- 读取原始进展
- 产出 completion evidence
- 报告健康事实

不负责：

- retry
- resubmit
- wait
- queue policy
- reply aggregation

### 5.5 每次 retry 都必须形成新 attempt

- 不能覆盖旧 attempt
- 不能覆盖旧 job
- 必须保留完整 lineage

### 5.6 广播可跨 agent 并发，单 agent 永远串行

- 一个消息可同时扇出到多个 agent
- 但对任意单个 agent，只能有一个 active inbound event

---

## 6. 总体分层

建议的新内核采用如下层级：

```text
CLI / MCP / Mail / Hooks
  -> Agent Compatibility Layer
  -> Mailbox Kernel
  -> Attempt Engine
  -> Provider Runtime Layer
  -> Completion Layer
  -> Durable Storage
```

### 6.1 Agent Compatibility Layer

负责：

- 保留 `agent_name` 作为公开 target
- 把现有 `ask/watch/pend/logs` 这类入口映射到新内核
- 向内核注入当前 agent runtime 上下文

### 6.2 Mailbox Kernel

负责：

- 每个 agent 的 inbox/outbox
- delivery lease
- 串行入站消费
- reply 回流再入 inbox

### 6.3 Attempt Engine

负责：

- `message -> attempt -> execution`
- retry / resubmit / supersede / dead-letter
- wait-any / wait-all / quorum
- fan-out / fan-in

### 6.4 Provider Runtime Layer

负责：

- 启动 provider backend
- 采集 provider-native 进展
- 输出统一 health snapshot

### 6.5 Completion Layer

负责：

- provider-specific completion detection
- 统一 `CompletionDecision`

### 6.6 Durable Storage

负责：

- mailbox 状态
- message / attempt / reply / inbound event 持久化
- restart recovery
- 死信与 lineage 追踪

---

## 7. 核心领域对象

### 7.1 AgentEndpoint

Agent 在新内核里不是一个普通 mailbox 地址，而是一个带执行上下文的端点：

```text
AgentEndpoint
- agent_name
- mailbox_id
- workspace_path
- runtime_ref
- session_ref
- provider_backend
- runtime_mode
- queue_policy
```

### 7.2 MailboxRecord

```text
MailboxRecord
- mailbox_id
- agent_name
- active_inbound_event_id
- queue_depth
- pending_reply_count
- last_inbound_started_at
- last_inbound_finished_at
- mailbox_state
- lease_version
```

### 7.3 MessageRecord

逻辑消息对象：

```text
MessageRecord
- message_id
- origin_message_id
- from_actor
- target_scope
- target_agents
- message_class
- reply_policy
- retry_policy
- priority
- payload_ref
- submission_id
- created_at
- updated_at
- message_state
```

### 7.4 AttemptRecord

具体执行尝试：

```text
AttemptRecord
- attempt_id
- message_id
- agent_name
- provider
- job_id
- retry_index
- health_snapshot_ref
- started_at
- updated_at
- attempt_state
```

### 7.5 InboundEventRecord

真正排在 agent inbox 里的对象：

```text
InboundEventRecord
- inbound_event_id
- agent_name
- event_type
- message_id
- attempt_id
- payload_ref
- priority
- status
- created_at
- started_at
- finished_at
```

建议的 `event_type`：

- `task_request`
- `task_reply`
- `completion_notice`
- `retry_signal`
- `system_signal`
- `barrier_release`

### 7.6 ReplyRecord

终态结果对象：

```text
ReplyRecord
- reply_id
- message_id
- attempt_id
- agent_name
- terminal_status
- reply
- diagnostics
- finished_at
```

### 7.7 DeliveryLease

控制 agent 单接收串行的关键对象：

```text
DeliveryLease
- agent_name
- inbound_event_id
- lease_version
- acquired_at
- last_progress_at
- expires_at
- lease_state
```

### 7.8 ProviderHealthSnapshot

provider/backend 的统一事实输出：

```text
ProviderHealthSnapshot
- job_id
- provider
- agent_name
- runtime_alive
- session_reachable
- progress_state
- completion_state
- last_progress_at
- observed_at
- degraded_reason
- diagnostics
```

---

## 8. 状态模型

### 8.1 MailboxState

```text
MailboxState
- idle
- delivering
- blocked
- recovering
- degraded
```

### 8.2 AttemptState

```text
AttemptState
- pending
- delivering
- running
- waiting_completion
- reply_ready
- stalled
- runtime_dead
- failed
- incomplete
- cancelled
- superseded
- dead_letter
- completed
```

### 8.3 MessageState

```text
MessageState
- created
- queued
- dispatching
- running
- partially_replied
- completed
- incomplete
- failed
- cancelled
- dead_letter
```

### 8.4 状态映射原则

provider 层的事实状态不能直接暴露给用户。

单向映射规则：

```text
ProviderHealthSnapshot + CompletionDecision + AgentRuntime
  -> AttemptState
AttemptState set + reply aggregation
  -> MessageState
```

---

## 9. 发送与接收语义

### 9.1 发送语义

- 同一个 agent 可以连续发很多条出站消息
- 出站消息进入 outbound log
- 发送动作本身不占用 inbound lease
- 阻塞/非阻塞只影响 sender 视角，不影响 receiver 的串行消费规则

### 9.2 接收语义

接收侧必须串行：

- 新任务进入 inbox
- reply 进入 inbox
- completion notice 进入 inbox
- 系统控制事件进入 inbox

入站消费是单线程语义，不允许并发插入执行。

### 9.3 回复语义

reply 的标准流转：

```text
attempt completed
  -> ReplyRecord created
  -> InboundEvent(type=task_reply) created
  -> enqueue into caller inbox
  -> wait for delivery lease
  -> caller consumes reply in order
```

---

## 10. 调度与队列模型

### 10.1 Outbox

用途：

- 记录 agent 发出去的逻辑消息
- 不阻塞发送
- 用于审计和相关性追踪

### 10.2 Message Queue

用途：

- 存储等待被转换成 attempt 的逻辑消息

### 10.3 Per-Agent Inbox Queue

用途：

- 存储所有入站事件
- 决定某个 agent 当前下一条要消费什么

### 10.4 Reply Aggregation Set

用途：

- 聚合多 agent 回复
- 实现 wait-any / wait-all / quorum

### 10.5 优先级建议

默认优先时间顺序，少量系统事件可升优。

建议优先级：

1. `system_signal`
2. `task_reply`
3. `completion_notice`
4. `task_request`
5. `retry_signal`

原则：

- 不做复杂的动态优先级算法
- 先保证可预测的顺序性和稳定性

---

## 11. Provider State Isolation

每个 provider 的状态判断可以完全不同，但只能体现在 **事实采集层**。

### 11.1 provider 层负责

- 如何启动
- 如何读取原始输出
- 如何判断 pane/session/runtime 是否还活着
- 如何提取 completion signal
- 如何生成 `ProviderHealthSnapshot`

### 11.2 bureau 层负责

- 把 snapshot 映射成 `AttemptState`
- 决定是否 retry / resubmit
- 决定是否 dead-letter
- 决定是否释放下一个 inbox event

### 11.3 provider 层绝不能负责

- queue policy
- reply aggregation
- retry/backoff
- wait semantics
- user-visible state names

---

## 12. Mailbox Kernel 内部服务

建议拆成以下服务，而不是一个大 manager。

### 12.1 MailboxService

职责：

- 管理 inbox / outbox
- 生成和消费 `InboundEventRecord`
- 管理 `DeliveryLease`

### 12.2 AttemptSupervisor

职责：

- 从 `MessageRecord` 生成 attempt
- 管理 retry/resubmit/supersede
- 保持 attempt lineage

### 12.3 LivenessService

职责：

- 读取 `ProviderHealthSnapshot` 与 runtime 事实
- 判定 `running/stalled/runtime_dead/orphaned`

### 12.4 ReplyAggregator

职责：

- 管 reply 汇总
- 支持 wait-one / wait-any / wait-all / quorum

### 12.5 RecoveryService

职责：

- askd restart recovery
- orphaned lease 恢复
- dead-letter 恢复

### 12.6 OperatorControlService

职责：

- 为 CLI / MCP / Mail 暴露控制接口
- 生成 queue / wait / retry / resubmit / barrier 等操作视图

---

## 13. 核心状态机

### 13.1 Mailbox Kernel 状态机

```text
idle
  -> (inbound event enqueued) -> blocked

blocked
  -> (lease acquired) -> delivering

delivering
  -> (event consumed terminally) -> idle or blocked
  -> (runtime lost / restart) -> recovering

recovering
  -> (lease recovered or released) -> blocked or idle

any
  -> (degraded backend facts) -> degraded
degraded
  -> (recovered) -> previous stable state
```

### 13.2 Inbound Event 状态机

```text
created
  -> queued
  -> delivering
  -> consumed
  -> superseded / abandoned
```

### 13.3 Attempt 状态机

```text
pending
  -> delivering
  -> running
  -> waiting_completion
  -> reply_ready
  -> completed

running
  -> stalled
  -> runtime_dead
  -> failed
  -> incomplete
  -> cancelled

stalled / runtime_dead / incomplete
  -> superseded (if retry)
  -> dead_letter (if policy stops)
```

### 13.4 Message 状态机

```text
created
  -> queued
  -> dispatching
  -> running
  -> partially_replied
  -> completed

running / partially_replied
  -> incomplete
  -> failed
  -> cancelled
  -> dead_letter
```

---

## 14. Wait / Blocking 语义

阻塞不是 backend 的行为，而是 caller 视角的 waiter。

### 14.1 必备 wait primitive

- `wait_job(job_id)`
- `wait_message(message_id)`
- `wait_any(group_id)`
- `wait_all(group_id)`
- `wait_quorum(group_id, min_replies=N)`

### 14.2 规则

- provider/backend 层不阻塞
- Mailbox Kernel 不阻塞 provider
- waiter 只监听状态机变化
- sender 可以选择阻塞等结果，但 receiver 的 inbox 串行消费规则不变

---

## 15. Retry / Resubmit / Dead-Letter

### 15.1 Retry

- 仍属于同一个 `message_id`
- 生成新的 `attempt_id`
- 通常目标 agent 不变
- 不覆盖旧 attempt

### 15.2 Resubmit

- 创建新的 `message_id`
- 通过 `origin_message_id` 指向旧消息
- 可以改 target、改 payload、改策略

### 15.3 Dead-Letter

以下情形可以进入 dead-letter：

- runtime 多次死亡
- stalled 超过策略上限
- terminal incomplete 且策略不允许继续 retry
- caller/target 环境长期不可恢复

---

## 16. 对外接口映射

### 16.1 公开接口继续保持 agent-first

- `ask <agent>`
- `ccb ask <agent>`
- `ccb watch <agent|job_id>`
- `ccb pend <agent|job_id>`
- `ccb wait <job_id|message_id>`（新增）
- `ccb queue <agent|all>`（新增）
- `ccb retry <job_id|attempt_id>`（新增）
- `ccb resubmit <message_id>`（新增）

### 16.2 MCP

MCP 不直接面向 provider，而是面向：

- `ccb_ask_agent`
- `ccb_pend_agent`
- `ccb_ping_agent`
- 未来可增加 `ccb_wait_message`

### 16.3 Mail

mail ingress 不直接触发 provider 提交：

- mail -> `MessageRecord`
- 再进入 Mailbox Kernel

mail egress 也不直接走 provider completion hook：

- reply -> caller inbox
- 由 egress policy 决定是否外发邮件

### 16.4 Completion Hook

completion hook 不应再视为“直达 caller 的回调器”，而应视为：

- terminal evidence ingress
- reply event creator
- mailbox notifier

---

## 17. 存储布局建议

建议在 `.ccb/askd/` 下新增 mailbox 相关持久化目录：

```text
.ccb/askd/
  mailboxes/
    <agent>/
      mailbox.json
      inbox.jsonl
      outbox.jsonl
  messages/
    messages.jsonl
  attempts/
    attempts.jsonl
  replies/
    replies.jsonl
  leases/
    <agent>.json
  dead-letters/
    dead_letters.jsonl
```

旧的 job / event / snapshot 存储可在过渡期保留，但不再作为系统主语。

---

## 18. 代码目录建议

推荐新目录：

```text
lib/mailbox_kernel/
  models.py
  store.py
  leases.py
  inbox.py
  outbox.py
  delivery.py

lib/message_bureau/
  models.py
  store.py
  attempts.py
  liveness.py
  aggregation.py
  recovery.py
  control.py

lib/provider_runtime/
  health.py
  adapters/
  polling/
```

这比继续把新逻辑堆到 `lib/askd/services/dispatcher_runtime/` 更干净。

---

## 19. 迁移策略

既然目标是能力和稳定性优先，迁移应以 **保持公开 agent-first 语义稳定** 为原则。

### Phase 0

- 冻结 provider-first 公共接口
- 明确 reply 必须回流 inbox

### Phase 1

- 新建 mailbox / message / attempt / reply / lease 模型与存储

### Phase 2

- 实现 Mailbox Kernel
- 让新任务与 reply 都进入 inbox

### Phase 3

- 实现 Attempt Engine
- 实现 retry/resubmit/dead-letter

### Phase 4

- 接入 provider health snapshot
- 接入 LivenessService / ReplyAggregator

### Phase 5

- 切换 CLI / MCP / mail / completion ingress 到新内核

### Phase 6

- 将旧 job-centric 上层降级为纯 execution backend 或逐步退休

---

## 20. 测试策略

### 20.1 模型测试

- record schema round-trip
- state transition validation
- retry lineage consistency

### 20.2 Mailbox 测试

- 单 agent 串行消费
- reply 重入 inbox
- broadcast 跨 agent 并发但单 agent 串行

### 20.3 Recovery 测试

- runtime dead
- stalled timeout
- askd restart orphan recovery
- dead-letter replay

### 20.4 黑盒测试

- `ask -> reply -> caller inbox`
- `wait_any / wait_all / quorum`
- `retry / resubmit`
- mail ingress / MCP ingress

---

## 21. 验收标准

新邮箱内核达到可用状态时，至少应满足：

- 所有公开提交接口仅接受 agent target
- 每个 agent 的入站事件严格串行
- reply 不存在旁路直达
- provider 状态差异被压在事实采集层
- user-facing 状态只暴露 mailbox / attempt / message 语义
- retry/resubmit 有完整谱系
- askd 重启后可以恢复 mailbox / lease / attempt 状态

---

## 22. 当前建议

当前最合理的下一步，不是继续增强 `JobDispatcher`，而是先落 **Phase 1 模型层**：

- `MailboxRecord`
- `MessageRecord`
- `AttemptRecord`
- `InboundEventRecord`
- `ReplyRecord`
- `DeliveryLease`
- `ProviderHealthSnapshot`

先把模型和存储做稳，再谈具体调度。
