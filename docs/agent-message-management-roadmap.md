# Agent Message Management Roadmap

Detailed design:

- see [`docs/agent-mailbox-kernel-design.md`](/home/bfly/yunwei/ccb_source/docs/agent-mailbox-kernel-design.md)

## Current Position

- baseline score: overall=50.33, structure=64.16, governance/full=36.49
- diff reading: overall=66.88, incremental=100.0, governance/full=36.49
- current reading: incremental changes are architecturally safe, but the repo-wide bottleneck remains governance and complexity concentration in `lib:askd`, which is exactly where the information-management layer must be anchored

## Existing Building Blocks

- `JobDispatcher` already owns durable submit/tick/complete/cancel transitions
- `JobStore`, `JobEventStore`, `SubmissionStore`, and snapshot writing already provide durable state and replay anchors
- `CompletionTrackerService` already separates execution from completion detection
- `AgentRegistry` and runtime sync already expose enough information to build liveness and queue views
- `watch/get/cancel` already cover a thin control plane, but they stop at single-job observation

## Hard Boundary

The provider/backend layer and the information-management layer must not share responsibility for policy.

### Provider/backend layer owns

- how a specific provider is started
- how provider-native progress is read
- how completion evidence is decoded
- how runtime/session/pane health is observed
- what provider-native failure reason or degraded signal was seen

### Information-management layer owns

- queue policy
- wait semantics
- retry/resubmit policy
- reply aggregation
- lineage and correlation
- operator-facing state model
- dead-letter and recovery workflow

That means provider code reports facts; the bureau decides policy.

## Provider State Isolation

Different providers absolutely should have different state judgment logic. The isolation point should be below askd orchestration, not mixed into retry or queue logic.

### Proposed bottom-layer split

```text
provider_execution
  -> transport/runtime adapter
  -> provider progress adapter
  -> completion detector
  -> provider health snapshot
```

### Recommended contracts

Add an explicit provider-facing status contract next to `ProviderSubmission` and `ProviderPollResult`.

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

```text
progress_state
  - not_started
  - submitted
  - accepted
  - actively_running
  - quiet_wait
  - output_advancing
  - stalled
  - runtime_lost
  - session_lost
  - unknown
```

```text
completion_state
  - not_complete
  - terminal_complete
  - terminal_incomplete
  - terminal_failed
  - terminal_cancelled
  - indeterminate
```

### Why this matters

- Claude, Codex, Gemini, OpenCode, and Droid each have different evidence models
- completion detectors already differ; health detectors should be allowed to differ too
- the bureau should never need to know whether a provider uses protocol turns, session boundaries, idle windows, or quiet text markers
- the bureau only needs a normalized health/state snapshot and terminal evidence

### Concrete provider responsibilities

- `provider_execution` adapter:
  - launch
  - restore
  - provider-native poll
  - emit raw progress items
  - emit `ProviderHealthSnapshot`
- `completion` layer:
  - convert raw progress into `CompletionItem`
  - maintain `CompletionDecision`
- `askd/runtime` layer:
  - provide `ProviderRuntimeContext`
  - update agent runtime registry and queue depth

## Bureau State Model

The information-management bureau should define its own operator-facing state model instead of reusing provider states directly.

```text
MessageState
  - queued
  - dispatching
  - running
  - waiting_replies
  - partially_replied
  - completed
  - incomplete
  - failed
  - cancelled
  - dead_letter
```

```text
AttemptState
  - pending
  - running
  - stalled
  - runtime_dead
  - abandoned
  - superseded
  - completed
  - incomplete
  - failed
  - cancelled
```

The mapping rule should be one-way:

- provider reports `ProviderHealthSnapshot`
- bureau maps snapshot + job status + policy into `AttemptState`
- user tools only consume `AttemptState` / `MessageState`

That keeps provider-specific complexity out of queue and retry logic.

## Current Gaps

- There is no first-class mailbox/channel abstraction above jobs, so request/reply correlation is still implicit
- Queue semantics are per-agent and local to the dispatcher, but not visible as a managed communication contract
- Blocking waits exist as client behavior (`ask --wait`, `watch_job`) rather than a reusable coordination primitive
- Runtime health is visible, but dead/alive/stalled distinctions are not promoted into a unified task policy layer
- Retry and resubmit are still operator actions, not policy-backed lifecycle features with lineage
- Fan-out/fan-in coordination is missing: broadcast exists, but not wait-all, quorum, barrier, or reply aggregation

## Message Bureau Services

The bureau should be split into small services rather than a single giant coordinator.

### 1. MailboxService

Responsibilities:

- create `message_id`
- own target group and correlation tags
- decide expected reply cardinality
- link submission/broadcast to one logical message

### 2. AttemptSupervisor

Responsibilities:

- create attempts from messages
- map `message -> attempt -> job`
- apply retry/resubmit policy
- mark an attempt as superseded, abandoned, or dead-lettered

### 3. LivenessService

Responsibilities:

- combine `AgentRegistry` runtime health with `ProviderHealthSnapshot`
- determine `running` vs `stalled` vs `runtime_dead`
- detect orphaned jobs after askd restart or runtime loss

### 4. ReplyAggregator

Responsibilities:

- collect replies across attempts
- support single, any, all, and quorum-style waits
- expose partial progress during fan-out
- decide when a logical message is complete

### 5. OperatorControl

Responsibilities:

- expose `wait`, `queue`, `retry`, `resubmit`, `barrier`
- render state summaries
- surface dead-letter items and recovery actions

## Dispatch And Receive Flow

### Send path

```text
public request
  -> MailboxService.create_message(...)
  -> AttemptSupervisor.start_attempt(...)
  -> JobDispatcher.submit(...)
  -> ExecutionService.start(...)
```

### Receive path

```text
provider poll
  -> ProviderHealthSnapshot + CompletionItem/Decision
  -> LivenessService.update_attempt_state(...)
  -> ReplyAggregator.ingest(...)
  -> MessageState recomputed
  -> completion notification / waiter wakeup / operator view update
```

### Retry path

```text
attempt terminal or unhealthy
  -> AttemptSupervisor.evaluate_policy(...)
  -> new attempt or dead-letter
  -> lineage updated
  -> prior attempt frozen, never overwritten
```

## Wait Semantics

Blocking and async should be implemented as views over the same state graph, not as separate execution modes.

### Required wait primitives

- `wait_job(job_id)`
- `wait_message(message_id)`
- `wait_any(submission_id)`
- `wait_all(submission_id)`
- `wait_quorum(submission_id, min_replies=N)`

### Rule

- provider layer never blocks
- bureau coordinates waiters
- CLI/MCP/mail only choose whether to block the caller or return immediately

That keeps blocking semantics out of the backend.

## Retry And Resubmit Design

Retry and resubmit are not the same thing and should be modeled separately.

### Retry

- same logical message
- same target agent unless policy says otherwise
- new attempt
- retains original correlation and mailbox identity

### Resubmit

- new logical message derived from a previous message
- may change target, payload, or policy
- links back through `origin_message_id`

### Recommended policy inputs

- runtime dead before first reply
- stalled beyond policy timeout
- terminal incomplete
- explicit operator action
- askd restart recovery outcome

## Recommended New Records

Add durable records for the bureau rather than overloading `JobRecord`.

```text
MessageRecord
  - message_id
  - origin_message_id
  - from_actor
  - target_scope
  - target_agents
  - reply_policy
  - retry_policy
  - created_at
  - updated_at
```

```text
AttemptRecord
  - attempt_id
  - message_id
  - job_id
  - agent_name
  - provider
  - attempt_state
  - retry_index
  - health_snapshot
  - started_at
  - updated_at
```

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

## Suggested Folder Shape

```text
lib/askd/services/message_bureau/
  models.py
  store.py
  mailbox.py
  attempts.py
  liveness.py
  aggregation.py
  waits.py
  control.py
```

## Immediate

- Keep the public interface strictly agent-only: no new provider-facing submit surfaces, aliases, or MCP tools
- Introduce a message-management document and backlog around `job`, `message`, `attempt`, and `reply` as separate concepts
- Add a durable `attempt_lineage` model so retry/resubmit is recorded instead of overwriting job history
- Add explicit `stalled` and `orphaned` lifecycle readings derived from runtime health plus completion silence
- Add a normalized `ProviderHealthSnapshot` contract below the bureau
- Expose queue depth, active job, last heartbeat, and last terminal decision in one management view

## Next

- Add a `MailboxService` above `JobDispatcher`
- Make mailbox concepts explicit:
  - `message_id`: stable logical request id
  - `attempt_id`: one concrete execution attempt
  - `reply_id`: one terminal response artifact
  - `channel`: target agent or broadcast group
- Add wait primitives:
  - `wait_one(message_id)`
  - `wait_all(submission_id)`
  - `wait_any(submission_id)`
  - `barrier(group_id)`
- Add retry policy objects:
  - `manual`
  - `on_dead_runtime`
  - `on_incomplete`
  - `bounded_backoff`
- Store retry/resubmit lineage so a user can see "original request -> attempt 2 -> attempt 3 -> final reply"
- Add `LivenessService` that maps provider health facts into bureau attempt states

## Later

- Add reply aggregation for broadcast and multi-agent workflows
- Add dead-letter storage for permanently failed or abandoned work
- Add channel-level flow control similar to MPI tags or communicators:
  - target group
  - message class
  - correlation tag
  - reply expectation
- Add scheduler policies beyond serial-per-agent:
  - weighted fairness
  - deadline priority
  - interactive vs batch lanes
- Add operator tooling for recovery:
  - `ccb retry <job_id>`
  - `ccb resubmit <job_id>`
  - `ccb wait <job_id|submission_id>`
  - `ccb queue <agent|all>`
  - `ccb barrier <group>`

## Proposed Model

### Layering

```text
CLI / MCP / Mail
  -> Message Management Layer
  -> JobDispatcher
  -> ProviderExecution
  -> CompletionTracker
  -> Storage / Runtime Registry
```

### Core Records

```text
MessageRecord
  - message_id
  - from_actor
  - target_scope
  - target_agents
  - body
  - policy
  - created_at

AttemptRecord
  - attempt_id
  - message_id
  - job_id
  - agent_name
  - status
  - runtime_health
  - retry_index
  - started_at
  - updated_at

ReplyRecord
  - reply_id
  - message_id
  - attempt_id
  - agent_name
  - terminal_status
  - reply_excerpt
  - finished_at
```

## Suggested Sequencing

1. Phase 1: Observability first
   - add `ProviderHealthSnapshot`, queue/liveness/attempt lineage records, and read APIs
2. Phase 2: Policy layer
   - add retry/resubmit/stalled detection without changing execution adapters
3. Phase 3: Coordination primitives
   - add wait-all/any, barrier, and reply aggregation
4. Phase 4: Public tooling
   - add `ccb wait/queue/retry/resubmit` and update MCP/mail surfaces to use message ids

## Why This Fits The Current Repo

- It reuses the durable job/event/snapshot system instead of replacing it
- It keeps provider implementations behind execution adapters only
- It lets agent-facing interfaces stay stable while richer orchestration grows above the dispatcher
- It matches the repo's existing split between execution, completion, runtime state, and CLI views
