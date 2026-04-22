# CCBD Startup And Supervision Contract

## 1. Purpose

This document defines the non-drifting contract for project-scoped startup, backend ownership, runtime supervision, pane recovery, and kill/shutdown behavior in `ccb_source`.

It is the authoritative design anchor for:

- `ccb` startup behavior
- `ccb open` attach behavior
- `ccbd` daemon lifecycle
- project-scoped runtime ownership
- configured-agent mounting
- pane/session/runtime recovery
- `ccb kill` semantics

The repo-local agent memory file [AGENTS.md](/home/bfly/yunwei/ccb_source/AGENTS.md) must always point back to this document rather than duplicating it.

Diagnostics-specific rules live in [docs/ccbd-diagnostics-contract.md](/home/bfly/yunwei/ccb_source/docs/ccbd-diagnostics-contract.md). Startup/shutdown behavior and diagnostics must evolve together.

Module/function-level redesign for the project-scoped mux namespace model lives in [docs/ccbd-project-namespace-lifecycle-plan.md](/home/bfly/yunwei/ccb_source/docs/ccbd-project-namespace-lifecycle-plan.md).

Detailed redesign for pane recovery layering and continuous foreground attach lives in [docs/ccbd-pane-recovery-continuous-attach-plan.md](/home/bfly/yunwei/ccb_source/docs/ccbd-pane-recovery-continuous-attach-plan.md).

User-facing config and mux layout rules live in [docs/ccb-config-layout-contract.md](/home/bfly/yunwei/ccb_source/docs/ccb-config-layout-contract.md). Startup behavior must honor that layout contract rather than inventing its own pane topology.

## 2. Problem Statement

The current codebase already contains pieces of the required behavior:

- project-scoped backend ownership via lease/lock
- runtime inspection and pane health checks
- provider-side `ensure_pane()` recovery hooks
- daemon restart-on-next-command behavior
- stop/kill cleanup logic

But those pieces do not currently form a single always-on control-plane contract.

The main failure mode is structural:

- startup authority is split across config, lease, runtime store, provider session files, and mux namespace facts
- runtime recovery is partially implemented but only executed on some paths
- pane death can mark an agent degraded without triggering a daemon-owned reconciliation loop
- shutdown behavior is split between server-side and CLI fallback logic

This document fixes the contract boundary first, so later implementation does not drift back into scattered patches.

## 3. Scope

In scope:

- one backend per `.ccb` anchor
- daemon startup and takeover rules
- configured-agent desired-state rules
- runtime supervision and recovery rules
- pane death handling
- records under `.ccb/ccbd/`
- `ccb kill` end-to-end semantics
- startup and recovery test matrix

Out of scope:

- provider-specific prompt/protocol details
- completion extraction policy
- mailbox/message semantics except where they depend on runtime liveness

## 4. Terms

- `project anchor`
  - the directory containing `.ccb/`
- `project backend`
  - the unique authoritative `ccbd` process for one project anchor
- `desired agents`
  - the configured agent set defined by `.ccb/ccb.config`
- `authority`
  - the state source allowed to define current project truth
- `evidence`
  - observable facts used for recovery decisions but not allowed to redefine authority
- `residue`
  - stale or extra state from previous runs, renames, or corruption; cleanup input only
- `runtime supervision`
  - the daemon-owned loop that keeps desired agents mounted and healthy
- `keeper`
  - a small watchdog process that restarts `ccbd` after crashes; it is not the project backend

## 5. Hard Contract

### 5.1 Project Scope

- One `.ccb` anchor defines one project control-plane scope.
- The directory that owns `.ccb/` is the only authority root for that project.
- Project lifecycle state must live under that project's `.ccb/` only.
- Startup, supervision, and shutdown must be reasoned per project anchor, never globally.

### 5.2 One Authoritative Backend

- Each project anchor may have at most one authoritative `ccbd` backend.
- `lease.json` plus startup lock plus socket ownership define backend authority.
- A second `ccbd` may only replace the current one through explicit takeover rules.
- Provider-specific background daemons must not become competing project authorities.

### 5.3 Desired Agent Set

- `.ccb/ccb.config` is the only forward authority for the project's desired agent mount set and foreground layout.
- `.ccb/ccb.config` logical names are also the only forward authority for project-namespace pane display names.
- Until a future explicit `enabled` or `desired_state` field exists, all configured agents are desired agents.
- `default_agents` and CLI `requested_agents` do not redefine long-lived backend ownership.
- `requested_agents` may affect foreground behavior or warm-start order only.

### 5.4 Authority Hierarchy

Authority order must be enforced exactly as follows:

1. `.ccb/ccb.config`
2. `.ccb/ccbd/lease.json`
3. `.ccb/ccbd/start-policy.json`
4. `.ccb/agents/<configured-agent>/runtime.json` for the current daemon generation

Evidence sources:

- provider session files
- mux pane liveness
- provider-runtime pid files
- runtime-root contents

Residue sources:

- `.ccb/agents/<unknown-agent>/`
- stale session files
- stale runtime files from previous generations
- malformed runtime files

Rules:

- evidence may guide recovery
- residue may guide cleanup
- configured-agent provider session files are agent-scoped by `.ccb/ccb.config` logical agent name
- provider-base session files such as `.codex-session` or `.claude-session` are legacy or unscoped evidence only:
  - they must not be reinterpreted as a configured agent's identity
  - they may be consulted only when no explicit agent binding is available
- residue such as provider session files or preserved workspaces must not by itself block config bootstrap
- neither evidence nor residue may silently redefine authority
- runtime pid loss is evidence only; for pane-backed runtime it must not preempt pane/session-based recovery checks

Missing-config recovery rules:

- if `.ccb/ccb.config` is missing and the anchor is otherwise empty, bootstrap may write the default config
- if `.ccb/ccb.config` is missing and `.ccb/agents/*/agent.json` provides a complete recoverable agent-spec set, bootstrap may reconstruct `.ccb/ccb.config` from those specs
- if `.ccb/ccb.config` is missing and authoritative state exists but agent specs are incomplete or malformed, startup must still fail clearly rather than inventing project truth

Runtime start policy rules:

- `.ccb/ccbd/start-policy.json` records the current project run's recovery startup policy
- `auto_permission` is inherited project runtime policy, not a one-shot pane-local flag
- recovery restore is not inherited from the original CLI invocation; daemon-owned recovery must always use restore semantics
- plain foreground `ccb` without explicit flags is defined as `restore=true` and `auto_permission=true`
- therefore:
  - explicit foreground `ccb` start uses the CLI-provided `restore` flag and `auto_permission` flag
  - daemon-owned recovery mount, pane recovery, namespace reflow, and post-crash remount must always use `restore=true`
  - those same daemon-owned recovery paths must reuse the persisted `auto_permission` policy from `.ccb/ccbd/start-policy.json`
- `ccb kill` / project stop-all must clear `.ccb/ccbd/start-policy.json`

### 5.5 Startup Transaction

Startup must be a single project-scoped transaction:

1. inspect anchor state
2. inspect config state
3. inspect backend lease/socket/heartbeat state
4. ensure project mux namespace
5. compute desired agents
6. compute recovery/start plan
7. commit startup actions
8. emit startup result and persist startup report

`start_status: ok` is valid only when:

- the project backend is healthy and authoritative
- the project namespace exists at the authoritative backend/session recorded under `.ccb/ccbd/`
- the project namespace has the current session-scoped CCB UI contract applied on that authoritative backend/session
- that project session contains the current namespace window contract:
  - one control window used as the long-lived session anchor
  - one workspace window used as the visible pane layout anchor
- project-generated namespace identifiers must remain mux-target-safe:
  - project namespace session names must be normalized before use as tmux-family targets
  - transient workspace reflow operations must address windows by tmux `window_id`, not temporary dotted window names
- config is valid for the current anchor
- desired agents have reached an acceptable mounted state

Acceptable mounted state means one of:

- healthy and attached
- recovering with explicit persisted reason and active reconcile ownership

It must never mean:

- stale binding accepted as success
- missing config silently replaced despite existing project state
- degraded runtime reported as healthy startup completion

Foreground command split:

- `ccb`
  - ensures backend authority
  - ensures the project mux namespace
  - ensures desired agents are mounted
  - plain `ccb` is the default interactive start path and implicitly includes `-a -r`
  - does not itself define UI attachment success
- `ccb -n`
  - is an explicit destructive project reset before start
  - must require interactive confirmation
  - must clear and rebuild all project-owned `.ccb` runtime state, logs, sessions, workspaces, and mail/message residue
  - must preserve `.ccb/ccb.config` exactly when it exists
  - if `.ccb/ccb.config` does not exist, startup may bootstrap the default config after reset
  - the same invocation must then continue through the normal `ccb` start transaction rather than using a separate startup implementation
  - that first post-reset startup must force `restore=false` so provider-global history cannot silently reattach old conversations
  - after the fresh post-reset startup completes, later ordinary `ccb` runs return to the default `-a -r` semantics
- `ccb open`
  - attaches to the existing project namespace only
  - must select the authoritative workspace window inside that session before attach completes
  - must not create a new daemon, namespace, or desired-agent plan
  - must fail clearly when namespace authority is absent

Project namespace compatibility:

- namespace `layout_version` covers visible pane topology and project-namespace mux UI contract, not just split geometry
- project namespace state must also persist the current visible layout signature produced from `.ccb/ccb.config` after foreground pruning
- when stored namespace `layout_version` differs from the current code contract, startup must recreate the project namespace rather than trying to mutate a stale session in place
- when the stored visible layout signature differs from the desired visible layout signature for the current foreground start, startup must recreate the project namespace rather than incrementally splitting an old pane tree
- when startup creates a fresh project namespace session, the root pane must begin as a silent placeholder process rather than an interactive shell
- for a fresh namespace, the `cmd` pane bootstrap happens only after layout finalization and must replace that silent placeholder in place
- startup must not rely on "real shell first, respawn later" behavior for the `cmd` pane, because that leaves stale prompt residue and can surface zsh no-newline `%` markers
- `cmd`-anchored projects must treat exact project-namespace pane membership as the reuse gate for pane-backed bindings
- for project-namespace reuse, exact membership means:
  - same authoritative backend ref for the project namespace (tmux socket path on Unix, named server ref on native Windows)
  - same authoritative tmux session
  - same logical `slot_key`
  - same current authoritative workspace `window_id`
- agent-only legacy layouts with `cmd` disabled may reuse instance-scoped provider session evidence when that session file does not explicitly declare a conflicting backend ref
- that legacy reuse exception is narrow:
  - if the session file explicitly declares a backend ref and it is not the project namespace ref, startup must reject it
  - if same-socket pane inspection proves the pane belongs to a detached sibling session or foreign project identity, startup must reject it
  - inferred default-server socket facts must not override an otherwise valid instance-scoped legacy binding

### 5.6 Runtime Supervision Is A Daemon Responsibility

The project backend must continuously keep desired agents mounted.

When `.ccb/ccb.config` enables `cmd`, the backend must also continuously keep the project-owned `cmd` slot present and healthy inside the authoritative workspace window.

This responsibility belongs to a daemon-owned supervision loop, not to:

- the next CLI command
- the next job start
- an incidental read path like `ps` or `doctor`
- health inspection paths such as `HealthMonitor.check_all()`

The supervision loop must run on backend heartbeat/tick and reconcile every desired agent, regardless of whether there is queued work.

For `cmd`-enabled projects:

- `cmd` is a project-namespace slot, not an entry in `AgentRegistry`
- `cmd` supervision must therefore happen at the namespace layer, not by pretending `cmd` is a provider runtime
- a healthy `cmd` slot means the authoritative workspace root pane still matches:
  - `role=cmd`
  - `slot_key=cmd`
  - `managed_by=ccbd`
  - current authoritative workspace `window_id`

### 5.7 Pane Death Recovery Contract

When a desired agent's pane dies, the daemon must reconcile it in the background using this order:

1. inspect current runtime authority
2. inspect provider session and terminal facts
3. if `ensure_pane()` can recover the pane, rebind runtime authority in place
4. if the original pane target is gone but the current project workspace window is still healthy, local recovery must create the replacement pane inside that current workspace window and immediately rebind it to the same logical `slot_key`
5. otherwise, if the project namespace session is still healthy and namespace-level repair is needed, reflow the workspace window inside that same session and relaunch the configured layout there
6. otherwise, if runtime facts prove session-level corruption and full project-wide reflow is safe, recreate the project namespace and relaunch the configured layout
7. otherwise tear down stale binding authority
8. relaunch runtime through the normal launch path
9. persist recovery result and retry/backoff state

Important rule:

- recovery must happen even if the agent is idle and no new job arrives
- when `cmd` is enabled, pane death or slot drift for `cmd` must also be detected and repaired on heartbeat even if no user command is running in that pane
- `cmd` recovery must first try session-preserving local slot replacement inside the current workspace window before escalating to project reflow
- ordinary `pane-dead` / `pane-missing` recovery must not use project-server destruction as the first-line path
- pane-backed runtime authority must carry `slot_key`, current workspace `window_id`, and `workspace_epoch`; pane id is evidence, not identity
- local replacement must target the authoritative current workspace window for that project session, not whichever backend target the provider runtime would create by default
- if local replacement changes pane id inside a project-owned namespace and project-wide reflow is currently safe, the daemon must immediately continue into session-preserving workspace reflow so the pane returns to canonical layout position
- session-preserving workspace reflow is the first namespace-level escalation for `pane_recovery:*`
- if local replacement cannot restore `cmd`, `cmd` slot recovery must escalate through that same session-preserving `pane_recovery:*` reflow path, with `pane_recovery:cmd` as the canonical reason
- if pane recovery is done by project-namespace reflow, pane position must return to the canonical layout derived from `.ccb/ccb.config`, not whichever slot the active mux backend happens to assign during local recovery
- workspace reflow must preserve the mux server/session; only the workspace window may be replaced
- recovery must always use restore semantics even if the original foreground `ccb` invocation did not pass `-r`
- recovery must inherit `auto_permission` from the persisted project start policy rather than falling back to hardcoded defaults

Project-namespace reflow safety rules:

- project-wide full reflow is an escalation path, not the default response to ordinary pane death
- session-preserving workspace reflow is allowed only when the affected runtime belongs to the project-owned namespace recorded under `.ccb/ccbd/`
- full project reflow is allowed only when the session itself is no longer a trustworthy repair boundary
- only reflow when no other configured agent is currently `BUSY`
- if reflow is not safe, fall back to local provider recovery rather than disrupting unrelated work

Project-socket cleanup rules:

- startup must compute the authoritative active pane set for the current project-owned namespace backend ref
- same-socket pane/session residue is evidence only; it must not be silently tolerated just because it lives on the project socket
- startup must clean project-owned orphan panes on the project socket during the startup transaction, not wait for a later manual cleanup path

### 5.8 Daemon Must Not Stay Dead

Strictly satisfying "backend must not die" requires a process outside `ccbd` itself.

Target architecture:

- `ccbd` remains the only authoritative project backend
- a lightweight project-scoped `keeper` process monitors it
- the keeper may restart `ccbd` after crashes
- the keeper never owns project runtime authority
- the keeper must reap exited direct children so crashed `ccbd` pids do not linger as zombie evidence
- keeper/CLI forced takeover is allowed only after the lease has entered a true takeover window:
  - `MISSING`
  - `UNMOUNTED`
  - `STALE`
- `DEGRADED` with a live pid plus fresh heartbeat is observation only, not restart authority, even if the project socket is temporarily unreachable
- therefore temporary UNIX-socket accept stalls during active work must surface as degraded availability, not a keeper-triggered daemon replacement

If keeper is absent, the system can only provide "restart on next `ccb` command", which is weaker than the target contract.

When `ccb` re-enters a project after an explicit shutdown, startup must first clear prior shutdown intent before keeper/daemon keepalive can resume.

### 5.9 Kill And Shutdown Transaction

`ccb kill` at the project anchor must execute a single shutdown transaction:

1. acquire shutdown intent
2. prevent keeper restart
3. stop new intake
4. stop running agent executions
5. stop all desired agents
6. destroy the project mux namespace at the project-owned backend/session
7. terminate surviving provider runtime pids that outlive namespace destruction
8. mark configured-agent runtime authority as stopped
9. unmount backend lease
10. close socket server
11. persist shutdown report

Shutdown must be best-effort toward residue and strict toward authority.

That means:

- malformed or unknown residue must not block kill
- configured-agent authority must end in a clean stopped/unmounted state
- once shutdown intent is acquired, the backend must not run any further reconcile/heartbeat tick that could remount desired agents during the same shutdown transaction
- local daemon shutdown helpers must not stop at `mark_unmounted()` plus socket close; they must run the same stop-all cleanup transaction first so provider-runtime pid files, namespace state, and configured-agent authority do not survive a backend-local shutdown

## 6. Required Runtime States

At minimum, the supervision model must distinguish these states:

- `unmounted`
- `starting`
- `healthy`
- `recovering`
- `degraded`
- `stopped`
- `failed`

For desired agents, `recovering` and `degraded` are not the same:

- `recovering`
  - daemon currently owns a live reconcile attempt
- `degraded`
  - agent is not healthy and no active recovery has yet succeeded

The current code already records `degraded`, but the target contract requires a distinct supervised recovery state.

## 7. Records Under .ccb

The following records are required.

### 7.1 Backend Authority

Path:

- `.ccb/ccbd/lease.json`
- `.ccb/ccbd/state.json`

Required fields:

- `project_id`
- `ccbd_pid`
- `namespace_epoch`
- `backend_family`
- `backend_impl`
- `ipc_kind`
- `ipc_ref`
- `session_name`
- `socket_path`
- `generation`
- `started_at`
- `last_heartbeat_at`
- `mount_state`
- `config_signature`
- optional `backend_ref`
- optional `tmux_socket_path`
- optional `tmux_session_name`
- optional `keeper_pid`
- optional `daemon_instance_id`

### 7.2 Startup Report

Path:

- `.ccb/ccbd/startup-report.json`

Required purpose:

- capture why startup succeeded, failed, took over, or recovered

Minimum content:

- anchor state
- config state
- daemon inspection
- desired agents
- actions taken
- final status

### 7.3 Supervision Event Log

Path:

- `.ccb/ccbd/supervision.jsonl`

Required purpose:

- append-only record of pane death detection, relaunch attempts, recovery failures, and success transitions

### 7.4 Agent Runtime Authority

Path:

- `.ccb/agents/<agent>/runtime.json`

Required fields beyond current baseline:

- `daemon_generation`
- `desired_state`
- `reconcile_state`
- `restart_count`
- `last_reconcile_at`
- `last_failure_reason`
- optional `backend_family`
- optional `backend_impl`
- optional `backend_ref`
- optional `session_name`
- optional `ipc_kind`
- optional `ipc_ref`
- optional `job_id`
- optional `job_owner_pid`
- optional `tmux_socket_name`
- optional `tmux_socket_path`

Unknown agent directories under `.ccb/agents/` are residue unless they are present in current config.

### 7.5 Keeper State

Path:

- `.ccb/ccbd/keeper.json`

Required purpose:

- record the project-scoped keeper process that currently owns daemon keepalive
- make keeper restart attempts and recent failure reason inspectable without treating keeper as backend authority

Minimum content:

- `project_id`
- `keeper_pid`
- `started_at`
- `last_check_at`
- `state`
- `restart_count`
- optional `last_restart_at`
- optional `last_failure_reason`

### 7.6 Shutdown Intent

Path:

- `.ccb/ccbd/shutdown-intent.json`

Required purpose:

- persist explicit shutdown intent so keeper will not restart `ccbd` during or after `ccb kill`

Minimum content:

- `project_id`
- `requested_at`
- `requested_by_pid`
- `reason`

### 7.7 Diagnostics Bundle

Command:

- `ccb doctor --bundle`

Required purpose:

- export a project-scoped support artifact that is sufficient for remote bug triage without interactive shell access

Required content:

- latest startup/shutdown/restore reports
- backend authority files
- backend stdout/stderr logs
- supervision and cleanup event history
- per-agent runtime authority and recent provider/runtime logs
- manifest rows that mark missing or truncated files explicitly

## 8. Implementation Shape

The design should converge toward these domains:

- `startup inspection`
- `startup policy`
- `startup transaction`
- `runtime supervision`
- `shutdown transaction`
- `reporting/read path`

Recommended module split:

- `lib/ccbd/startup/inspection.py`
- `lib/ccbd/startup/policy.py`
- `lib/ccbd/startup/transaction.py`
- `lib/ccbd/supervision/inspector.py`
- `lib/ccbd/supervision/loop.py`
- `lib/ccbd/shutdown/transaction.py`
- `lib/ccbd/reports/startup_report.py`

The key rule is not the exact package name. The key rule is separation:

- inspect first
- decide next
- mutate last

## 9. Current Code Alignment And Gap

The current code already aligns with the contract in some places:

- unique backend ownership is partly enforced by `OwnershipGuard`
- heartbeat and lease refresh exist in `CcbdApp`
- pane/session inspection exists in `HealthMonitor`
- provider recovery hooks exist through `ensure_pane()`
- runtime relaunch support exists in the runtime launch path

But there is one critical gap:

- recovery is not owned by a continuous daemon supervision loop

Current behavior:

- `HealthMonitor` can detect pane death and sometimes repair bindings
- further recovery is mainly attempted when a new job is about to start

Target behavior:

- daemon heartbeat itself must reconcile desired agents continuously

This gap is the main reason the current system can appear to "know how to recover" but still fail to keep idle agents mounted after pane death.

## 10. Phased Delivery

### Phase A: Contract Preservation

- keep one authoritative backend per anchor
- keep config as desired-agent authority
- keep residue from blocking kill
- stop silent authority drift

### Phase B: Runtime Supervision Loop

- add daemon-owned reconcile loop for all desired agents
- recover pane death without waiting for job start
- persist supervision state and retry/backoff

### Phase C: Keeper

- add project-scoped keeper
- restart `ccbd` after crash
- respect shutdown intent so `ccb kill` remains authoritative

### Phase D: Unified Reports

- startup report
- supervision event log
- shutdown report
- read paths consume reports instead of inferring partial truth ad hoc

## 11. Acceptance Matrix

The design is not complete until the following scenarios are automated and green.

Anchor and config:

- `.ccb` missing
- `.ccb` empty
- `.ccb` exists with persisted state but missing config
- config malformed
- config changed while backend is alive

Backend ownership:

- healthy mounted daemon
- stale lease with dead pid
- mounted lease with dead socket
- healthy lease with config mismatch
- backend crash while keeper is active
- explicit `ccb kill` does not trigger keeper restart

Runtime supervision:

- stale binding on startup
- pane dies while agent is idle
- pane dies while agent has queued work
- `ensure_pane()` succeeds
- `ensure_pane()` fails and relaunch succeeds
- repeated relaunch failure enters backoff/recovering state

Shutdown:

- normal `ccb kill`
- forced `ccb kill -f`
- unknown stale agent directories exist
- malformed runtime residue exists
- project-owned panes are removed
- backend lease ends unmounted

## 12. Change Discipline

If future work changes any of the following, this document must be updated in the same patch:

- who owns backend authority
- what defines desired agents
- whether daemon or job path owns runtime recovery
- whether keeper exists and what it is allowed to do
- what `ccb kill` guarantees
- what files under `.ccb/ccbd/` are authoritative

If implementation and this document disagree, the disagreement must be treated as an architecture issue, not hand-waved as an implementation detail.
