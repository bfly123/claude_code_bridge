# Current Project Structure

This document records the current repo layout after the agent-first
provider-backend migration cleanup.

It is intentionally practical: it describes what exists now, which
directories are part of the active runtime, and where the largest
remaining structural debt still sits.

The current runtime authority is `ccbd`. Some deeper historical sections
below still mention older `askd` naming where the full document rewrite
has not yet landed; treat those as migration debt, not current authority.

## Runtime Spine

The current agent-first runtime flows through this chain:

```text
ccb
  -> lib/cli/*
  -> lib/ccbd/*
  -> lib/provider_execution/*
  -> lib/completion/*
  -> lib/storage/* + lib/project/* + lib/workspace/*
```

The root entrypoint is now intentionally thin:

- `ccb`
  compatibility facade plus CLI handoff
- `lib/launcher/app.py`
  launcher compatibility composition root for pane/session-oriented legacy surfaces
- `lib/launcher/bootstrap/`
  launcher bootstrap contracts, lifecycle adapters, and service wiring
- `lib/launcher/bootstrap/builders/`
  grouped service-construction builders for core/store/launcher/runup assembly
- `lib/launcher/app_deps.py`
  compatibility wrapper for bootstrap dependency bindings
- `lib/launcher/app_project.py`
  project/config/session-path helpers
- `lib/launcher/app_runtime.py`
  pane/session/runtime helper mixin for the compatibility launcher shell
- `lib/launcher/app_facade.py`
  compatibility wrapper for launcher facade mixins
- `lib/launcher/facade/`
  provider-facing facade helpers and mixins grouped by tmux/current-pane/claude concerns
  target-facing facade wrappers are now grouped under
  `launcher/facade/targets_runtime/`; `targets.py` remains a stable
  re-export surface
- `lib/launcher/commands/`
  provider-specific start-command and resume/autoconfig helpers
- `lib/launcher/commands/providers/`
  per-provider launcher command builders and resume/config detection split by provider
- `lib/launcher/commands/factory.py`
  launcher start-command factory implementation; top-level `start_commands.py` remains compatibility-only
  Codex provider internals are now split between history detection, auto-approval config, and command assembly
  OpenCode provider internals are now split between resume detection, local config mutation, and command assembly
- `lib/launcher/ops/`
  target start operations split by tmux/current-pane/claude flows
- `lib/launcher/ops/current/`
  current-pane target operations split by codex, shell-like targets, and router dispatch
- `lib/launcher/maintenance/`
  path normalization, shell command builders, runtime helpers, and runtime cleanup
- `lib/launcher/maintenance/runtime/`
  runtime env parsing, git metadata, temp cleanup, runtime GC, and log shrink helpers
- `lib/launcher/session/`
  launcher session JSON I/O, registry payload builders, and provider-specific session metadata helpers
  target-session writes and registry update paths are further separated so store classes stay coordination-focused
- `lib/launcher/app_bootstrap.py`
  compatibility re-export layer

The provider layer is split into:

```text
lib/provider_core/*
lib/provider_backends/<provider>/*
lib/provider_backends/pane_log_support/*
```

Meaning:

- `provider_core` holds shared provider metadata, runtime specs, and registry contracts
- `provider_backends` owns backend-specific session, protocol, comm, and
  execution helpers
- `provider_backends/pane_log_support/` holds shared raw pane-log reader
  and communicator base logic for shell-style providers that do not emit
  structured session logs
- `provider_execution` is the runtime-facing execution layer used by the
  agent-first flow

## Directory Roles

### Active runtime directories

- `lib/cli/`
  phase-2 parsing, rendering, context construction, and non-phase2
  command routing
  phase-2 reply/mailbox/ops rendering is now grouped under
  `cli/render_runtime/`, leaving `render.py` as the stable render facade
  instead of another mixed output-formatting file
  mailbox/job/trace/ack render helpers there are now also grouped under
  `cli/render_runtime/mailbox_views_runtime/`, leaving
  `render_runtime/mailbox_views.py` as the stable mailbox-render facade
  instead of a flat multi-view formatter
  phase-2 command dispatch, context bootstrap, reset confirmation, and
  handler routing are now grouped under `cli/phase2_runtime/`, leaving
  `phase2.py` as the stable entry facade and monkeypatch surface
  kill-command zombie cleanup, provider session teardown, and daemon
  termination helpers are now grouped under `cli/kill_runtime/`,
  leaving `cli/kill.py` as the stable command facade and monkeypatch
  surface
  phase-2 project kill shutdown preparation, pid ownership cleanup, and
  shutdown-report assembly are now also grouped under
  `cli/services/kill_runtime/`, leaving `services/kill.py` as the
  stable project-kill facade and monkeypatch surface
  project-kill pid candidate collection, procfs matching, and
  termination helpers now also reuse the shared
  `runtime_pid_cleanup/` package so CLI shutdown does not own a second
  copy of project pid-lifecycle logic
  tmux project-pane enumeration, socket-aware orphan cleanup, and
  current-pane-last kill ordering are now also grouped under
  `cli/services/tmux_project_cleanup_runtime/`, leaving
  `services/tmux_project_cleanup.py` as the stable cleanup facade and
  monkeypatch surface for tmux availability/current-pane tests
  CLI install/update/version helpers are now grouped under
  `cli/management_runtime/`, leaving `cli/management.py` as a stable
  facade for management command handlers
  remote tag fetch, release metadata transport, and local version-format
  helpers there are now further grouped under
  `cli/management_runtime/versioning_runtime/`, leaving
  `versioning.py` as the stable version-query facade instead of another
  flat network/formatting file
  phase-2 command parsing is now grouped under `cli/parser_runtime/`,
  separating ask/start parsing, shared argparse helpers, general
  subcommand parsers, and fault parsing so `cli/parser.py` stays as the
  stable phase-2 facade
  start-time project-config validation, provider parsing, lock reuse,
  and selection helpers are now grouped under `cli/start_runtime/`,
  leaving `cli/start.py` as the stable start helper facade
  daemon startup readiness, keeper handoff, and shutdown sequencing are
  now grouped under `cli/services/daemon_runtime/`, leaving
  `services/daemon.py` as the stable daemon facade and monkeypatch
  surface for startup/keeper tests
  runtime launcher pane creation/fallback and session-file writes are
  now grouped under `cli/services/runtime_launch_runtime/`, leaving
  `services/runtime_launch.py` focused on gate checks, launcher
  selection, and monkeypatch-stable wrapper helpers
  tmux binding liveness checks and stale-pane cleanup there are now
  further grouped under
  `cli/services/runtime_launch_runtime/binding_state_runtime/`, leaving
  `binding_state.py` as the stable binding-state facade instead of a
  mixed liveness/cleanup helper
  runtime-binding liveness and stale-pane cleanup there are now also
  grouped under package-local runtime modules, so the public
  `runtime_launch.py` surface keeps test/compat injection points
  without owning the full branchy launch gate logic
  async wait polling, quorum policy, and reply reduction are now also
  grouped under `cli/services/wait_runtime/`, leaving `services/wait.py`
  as the stable wait facade and monkeypatch surface
  provider session binding lookup now treats
  `services/provider_binding.py` as a thin compatibility facade over the
  shared `provider_core/session_binding_evidence.py` adapter instead of a
  CLI-owned authority source
- `lib/ccbd/`
  project-scoped control plane for startup, supervision, namespace
  lifecycle, dispatcher flow, and shutdown/reporting
  keeper state records, shutdown intent persistence, and restart/backoff
  helpers are now grouped under `ccbd/keeper_runtime/`, leaving
  `keeper.py` focused on the project keeper loop and the test-visible
  process helpers that still need a stable monkeypatch surface
  lifecycle report model families are now grouped under
  `ccbd/models_runtime/lifecycle_runtime/`, separating cleanup-summary,
  runtime-snapshot, startup-report, and shutdown-report schemas so
  `models_runtime/lifecycle.py` stays as the stable lifecycle-model
  facade instead of a single record pile
  ping payload assembly and summary-store reads are now grouped under
  `ccbd/handlers/ping_runtime/`, leaving `handlers/ping.py` as the
  stable ping-handler facade instead of mixing agent/daemon payload
  shaping with store reads
  per-agent startup preparation is now grouped in
  `ccbd/start_preparation.py`, leaving `start_flow.py` focused on startup
  orchestration, layout application, runtime attach, and cleanup
  startup runtime details are now grouped under `ccbd/start_runtime/`,
  separating tmux layout gating, provider-binding usability checks,
  cmd-pane bootstrap, per-agent runtime attach, and start-time orphan
  cleanup from the stable `start_flow.py` facade
  project-namespace binding validation, socket declaration reads, and
  pane relabel/start hints there are now further grouped under
  `ccbd/start_runtime/binding_runtime/`, leaving
  `start_runtime/binding.py` as the stable binding facade instead of
  another flat evidence file
  supervision recovery, mount, and backoff logic are now grouped under
  `ccbd/supervision/*.py`, leaving `supervision/loop.py` as the stable
  heartbeat/reconcile facade instead of a flat state-machine file
  stop-all shutdown execution and pid/tmux cleanup are now grouped in
  `ccbd/stop_flow.py`, leaving `supervisor.py` focused on orchestration
  and lifecycle reporting
  supervisor namespace handoff, start/stop orchestration, and
  startup/shutdown report assembly are now also grouped under
  `ccbd/supervisor_runtime/`, leaving `supervisor.py` as the stable
  orchestration facade and monkeypatch surface for start-flow tests
  stop-time runtime selection, pid cleanup, tmux orphan cleanup, and
  shutdown snapshot helpers are now further grouped under
  `ccbd/stop_flow_runtime/`, so `stop_flow.py` stays as the stable
  shutdown facade instead of another mixed teardown file
  daemon stop-flow pid candidate collection, procfs reads, and
  termination helpers there now also reuse the shared
  `runtime_pid_cleanup/` package so ccbd and CLI shutdown paths consume
  one project-pid ownership implementation
  provider pane assessment for health supervision is now grouped under
  `ccbd/services/health_assessment/`, leaving
  `services/health_runtime.py` as the stable assessment facade; health
  monitor orchestration, pane-state routing, and runtime update helpers
  are now grouped under `ccbd/services/health_monitor_runtime/`,
  leaving `services/health.py` as the stable health-monitor facade
  degraded-state field updates, rebind writes, and provider-fact
  projection there are now further grouped under
  `ccbd/services/health_monitor_runtime/updates_runtime/`, so the
  health-monitor facade no longer mixes degraded-pane state retention
  with rebind/update helper details
  dispatcher start/recovery/queue tick helpers are now grouped under
  `ccbd/services/dispatcher_runtime/lifecycle_start_runtime/`, leaving
  `dispatcher_runtime/lifecycle_start.py` as the stable dispatcher
  startup facade instead of another flat reconcile file
  completion snapshot writes and terminal decision/state merges are now
  also grouped under `ccbd/services/dispatcher_runtime/completion_runtime/`,
  leaving `dispatcher_runtime/completion.py` as the stable completion
  facade instead of another mixed state-merge file
  dispatcher retry-policy evaluation, timeout inspection notices, and
  retry/non-retryable failure reply shaping are now also grouped under
  `ccbd/services/dispatcher_runtime/finalization_retry_runtime/`,
  leaving `dispatcher_runtime/finalization_retry.py` as the stable
  retry/reply facade
  reply-delivery claim, head-rewrite, payload-formatting, and terminal
  requeue/consume flows are now also grouped under
  `ccbd/services/dispatcher_runtime/reply_delivery_runtime/`, leaving
  `dispatcher_runtime/reply_delivery.py` as the stable reply-delivery
  facade instead of another mixed mailbox/payload file
  runtime attach, restore/readiness, and provider-binding refresh flows
  are now grouped under `ccbd/services/runtime_runtime/`, leaving
  `services/runtime.py` as the stable service facade instead of a mixed
  lifecycle/state-update file
  tmux-specific pane backend/ownership/namespace checks for health
  assessment are now also grouped under
  `ccbd/services/health_assessment/tmux_runtime/`, leaving
  `health_assessment/tmux.py` as the stable tmux-assessment facade
  project namespace tmux backend lifecycle, state/event record shaping,
  and ensure/destroy flows are now also grouped under
  `ccbd/services/project_namespace_runtime/`, leaving
  `services/project_namespace.py` as the stable namespace-controller
  facade
- `lib/askd/`
  project-scoped ask daemon app, socket server/client, handlers, mount
  state, and restore paths
  `askd.client` is now mostly a legacy facade over
  `askd/client_runtime/`; provider wrapper main paths have been moved to
  native askd socket jobs, and the remaining facade usage is isolated to
  compat/diagnostic surfaces pending retirement
  `askd.server` is now a package facade over `askd/server_runtime/`
  environment, handler, state-write, server bootstrap, and lifecycle
  monitor modules
  standalone askd worker routing, request handling, and runtime
  state cleanup now live under `askd/daemon_runtime/`, leaving
  `askd/daemon.py` as the standalone askd entry facade
  dispatcher coordination internals are now grouped under
  `askd/services/dispatcher_runtime/` so `services/dispatcher.py`
  stays focused on submit/tick/complete orchestration; polling, restore
  replay, watch-target routing, and completion-state helpers now live in
  package-local runtime modules there
  submit/tick lifecycle orchestration and cancel-terminalization helpers
  are now further separated into dedicated `dispatcher_runtime/`
  modules, reducing `services/dispatcher.py` to the dispatcher facade
  and shared store/runtime helpers
  Claude adapter reply-shaping and wait/finalize helpers are now grouped
  under `askd/adapters/claude_runtime/`, leaving
  `askd/adapters/claude.py` as a provider-facing orchestration facade
  Claude reply postprocessing there is now further separated into intent
  detection, table normalization, and format-repair modules so
  `claude_runtime/reply_postprocess.py` stays as the orchestration
  facade instead of a single rule pile
  Codex and Gemini ask-daemon wait/finalize flows are now also grouped
  under `askd/adapters/codex_runtime/` and
  `askd/adapters/gemini_runtime/`, leaving their adapter modules focused
  on session/backend wiring
  OpenCode and Droid ask-daemon wait/finalize flows are now also grouped
  under `askd/adapters/opencode_runtime/` and
  `askd/adapters/droid_runtime/`, leaving their adapter modules focused
  on session/backend wiring
  CodeBuddy, Qwen, and Copilot ask-daemon wait/finalize flows are now
  also grouped under `askd/adapters/codebuddy_runtime/`,
  `askd/adapters/qwen_runtime/`, and `askd/adapters/copilot_runtime/`,
  leaving their adapter modules focused on session/backend wiring
  Codex ask-daemon wait-loop, reply cleanup, and completion-hook notify
  helpers there are now further split into dedicated task-runtime
  helper modules so `codex_runtime/task_runtime.py` stays as a stable
  import facade instead of another flat loop pile
  ask-daemon RPC/dataclass payload families now live under
  `askd/api_models_runtime/`, leaving `askd/api_models.py` as a stable
  import facade instead of a single record pile
  ask-daemon lease and restore-report dataclasses now also live under
  `askd/models_runtime/`, leaving `askd/models.py` as the stable schema
  facade
  `lib/ask_cli/` is now alias-only: `ask_cli.main` forwards `ask` to the
  canonical `ccb ask` phase-2 path, and programmatic callers no longer
  use a separate `ask_cli.runtime` helper layer
  legacy top-level `askd_client.py`, `askd_runtime.py`, and
  `askd_server.py` now remain as compatibility shims only
- `lib/agents/`
  agent config schema, runtime state records, restore checkpoints,
  policy defaults, and persistent stores
  `agents.models` is now a stable facade over `agents/models_runtime/`,
  with name normalization, enums, config dataclasses, and runtime
  dataclasses separated into package-local modules
  agent-spec normalization and project-layout validation there are now
  further grouped under `agents/models_runtime/config_runtime/`, leaving
  `models_runtime/config.py` as the stable config facade instead of a
  single validation-heavy dataclass file
  `agents.config_loader` is now a stable facade over
  `agents/config_loader_runtime/`, with compact config loading, validation,
  default-template rendering, and config-path helpers separated into
  dedicated modules
  config grammar validation and bootstrap/residue recovery there are now
  further grouped under `agents/config_loader_runtime/parsing_runtime/`
  and `agents/config_loader_runtime/io_runtime/`, leaving
  `parsing.py` and `io.py` as stable loader facades instead of mixed
  document/bootstrap modules
- `lib/memory/`
  session parsing, dedupe, transfer orchestration, and transfer-context
  formatting
  formatter helpers there are now grouped under
  `memory/formatter_runtime/`, separating provider label/timestamp
  helpers, tool/stat rendering, and format-specific output assembly so
  `formatter.py` stays as the stable formatter facade
  formatter tool-input shaping, tool execution rendering, and stats
  block assembly there are now also grouped under
  `memory/formatter_runtime/tools_runtime/`, leaving `tools.py` as the
  stable tool-formatting facade instead of another mixed helper file
  session-stat extraction there is now also grouped under
  `memory/session_parser_runtime/stats_runtime/`, separating session-file
  iteration from tool/file/task aggregation so `stats.py` stays as the
  stable stats facade instead of another mixed parsing file
- `lib/mail/`
  email ingress, routing, polling, sending, and ask-bridge integration
  mail ask submission/context helpers are now grouped under
  `mail/ask_runtime/`, leaving `mail/ask_handler.py` focused on
  message normalization and orchestration instead of mixing context
  persistence, environment assembly, and ask submission details
- `lib/mailbox_kernel/`
  mailbox event, lease, and mailbox-state coordination for per-agent
  delivery
  event queries, claim/ack transitions, and mailbox refresh projection
  are now grouped under `mailbox_kernel/service_runtime/`, leaving
  `service.py` as the stable mailbox-kernel facade instead of a mixed
  state-machine/projection file
- `lib/message_bureau/`
  bureau control/reporting views, queue inspection, replies, and trace
  assembly
  queue/inbox/ack view helpers are now grouped under
  `message_bureau/control_queue_runtime/`, separating mailbox target
  resolution, pending-event shaping, summary views, and ack completion
  so `control_queue.py` stays as the stable facade
- `lib/provider_execution/`
  execution registry, provider adapters, state persistence, and restore
  orchestration
  execution-service replay/persist/restore flows now live under
  `provider_execution/service_runtime/`, leaving `service.py` as the
  stable coordination facade instead of the full state-machine body
  shared active-runtime start/poll/resume guards now live under
  `provider_execution/active_runtime/`, leaving `active.py` as the
  stable facade while start preparation, poll guards, pane-liveness
  checks, and resume wiring stay separated inside the shared execution
  contract
  fake provider directive parsing, default script generation, and
  payload/terminal-decision helpers now live under
  `provider_execution/fake_runtime/`, leaving `fake.py` as the stable
  adapter facade for execution-service tests and provider registry
  wiring
  shared item building, runtime-state serialization, path/session
  preference, and pane-target terminal helpers now also live under
  `provider_execution/common_runtime/`, leaving `common.py` as the
  stable shared-helper facade instead of accumulating unrelated utility
  contracts
- `lib/provider_hooks/`
  provider completion-hook command building and workspace settings/trust
  installation
  provider hook env merge, per-provider command installation, and trust
  writers now live under `provider_hooks/settings_runtime/`, leaving
  `settings.py` as the stable hook-settings facade instead of a mixed
  JSON/env mutation file
- `lib/provider_sessions/`
  shared project session-path lookup, writable checks, and atomic
  session-file writes
  path resolution, binding-aware session discovery, writable-state
  validation, and safe-write helpers are now grouped under
  `provider_sessions/files_runtime/`, leaving `files.py` as the stable
  session-files facade
- `lib/provider_core/`
  shared provider manifests, registry surfaces, path/session naming, and
  compatibility glue
  builtin backend assembly and fake-provider backend assembly now live
  under `provider_core/registry_runtime/`, leaving `registry.py`
  focused on the public registry surface and default builder entrypoints
  provider session evidence extraction and pane-ownership-backed binding
  facts now also live under `provider_core/session_binding_evidence.py`
  so `ccbd` startup/health and CLI compatibility surfaces consume the
  same adapter instead of interpreting provider session files separately
  provider session-field extraction, pane-state inspection, root/session
  loading, and usable-binding validation are now further grouped under
  `provider_core/session_binding_evidence_runtime/`, leaving
  `session_binding_evidence.py` as the stable shared-evidence facade
  tmux session identity extraction, title resolution, ownership
  inspection, and mismatch text rendering are now also grouped under
  `provider_core/tmux_ownership_runtime/`, leaving
  `tmux_ownership.py` as the stable pane-ownership facade
- `lib/provider_backends/`
  backend-owned implementations for codex, claude, gemini, opencode,
  droid, codebuddy, copilot, and qwen
  Codex log-binding and JSONL parsing support is now grouped under
  `provider_backends/codex/comm_runtime/`; session discovery, tmux
  health checks, communicator session state/send flows, binding
  persistence, JSONL parsing, incremental log-reader polling, and
  watchdog callback handling now live there so `codex/comm.py` is
  reduced to the provider-facing facade and stable monkeypatch surface;
  `CodexCommunicator` and `CodexLogReader` class bodies now also live in
  runtime-local facade modules there
  Codex communicator internals there are now further separated into
  session-state, terminal-health, and send/wait modules so
  `comm_runtime/communicator.py` stays as a stable import facade
  Codex reader internals are now further separated there into debug
  helpers, log path/work-dir selection, state snapshots, tail-content
  reads, and incremental polling modules so `comm_runtime/log_reader.py`
  stays as a thin import surface instead of another monolith
  Codex log-entry normalization and assistant/user message extraction
  are now also grouped under `comm_runtime/log_entries_runtime/`,
  leaving `log_entries.py` as the stable parsing facade instead of
  mixing entry coercion with message shaping
  Codex polling read-loop state there is now also grouped under
  `comm_runtime/polling_runtime/`, separating read cursor state,
  line-decoding/match extraction, and log-switch handling so
  `polling.py` stays as the stable facade
  Codex active execution start/resume wiring and protocol polling logic
  are now grouped under `provider_backends/codex/execution_runtime/`,
  leaving `codex/execution.py` as the adapter facade and stable
  monkeypatch surface for execution tests
  Codex provider launch runtime preparation, resume-session lookup,
  home/profile isolation, and bridge spawn helpers now also live under
  `provider_backends/codex/launcher_runtime/`, leaving
  `codex/launcher.py` as the stable launcher facade instead of another
  provider-specific coordination file
  Codex execution polling there is now further separated into entry
  reading, reply-selection helpers, and poll-state transition modules so
  `execution_runtime/polling.py` remains the orchestration facade
  Codex execution poll-state handling there is now also grouped under
  `execution_runtime/state_machine_runtime/`, separating poll state,
  binding updates, user/assistant/terminal entry handling, and
  finalization so `state_machine.py` stays as the stable facade
  Codex project-session binding updates there are now also grouped under
  `comm_runtime/binding_update_runtime/`, separating project-session
  mutation, old-binding transfer, registry publication, and persistence
  so `binding_update.py` stays as a stable facade instead of another
  mixed runtime file
  Codex bridge env/session helpers, binding-tracker refresh, and bridge
  service lifecycle are now also grouped under
  `provider_backends/codex/bridge_runtime/`, leaving `codex/bridge.py`
  as the stable bridge facade for runtime entrypoints and tests
  Codex workspace-session tail scans and latest-log selection there are
  now also grouped under `comm_runtime/session_selection_runtime/`,
  separating reverse-tail reads, workspace session follow state, and
  scan policy so `session_selection.py` stays as the stable facade
  Codex project-session file lookup, pane self-heal, and log-binding
  persistence now also live under
  `provider_backends/codex/session_runtime/`, leaving `codex/session.py`
  as the stable session facade
  Codex resume-command parsing, command rewriting, and persisted
  start-cmd field selection are now also grouped under
  `provider_backends/codex/start_cmd_runtime/`, leaving
  `codex/start_cmd.py` as the stable resume-command facade
  Gemini project-hash detection, session selection, JSON session-file
  reads, incremental polling, and watchdog update support are now
  grouped under `provider_backends/gemini/comm_runtime/`, leaving
  `gemini/comm.py` as the provider-facing facade and stable monkeypatch
  surface; `GeminiCommunicator` and `GeminiLogReader` class bodies now
  live in runtime-local facade modules there, while communicator
  lifecycle, health checks, session-binding updates, and send/wait
  orchestration stay in that runtime package
  Gemini communicator internals there are now further grouped under
  `comm_runtime/communicator_runtime/`, separating communicator state,
  binding publication, health checks, and ask/consume flows so
  `comm_runtime/communicator.py` stays as the stable import facade
  Gemini project-session binding updates there are now also grouped
  under `comm_runtime/binding_update_runtime/`, separating
  project-session mutation, old-binding transfer, registry publication,
  and persistence so `binding_update.py` stays as a stable facade
  Gemini reader internals are now further separated there into debug,
  state initialization, session selection, session-content reads, and
  polling modules so `comm_runtime/log_reader.py` stays as a thin import
  surface and `gemini/comm.py` no longer carries the full reader body
  Gemini project-hash normalization, candidate derivation, registry
  work-dir lookup, and session-id reads there are now also grouped
  under `comm_runtime/project_hash_runtime/`, leaving
  `project_hash.py` as the stable facade instead of another mixed path
  and filesystem helper file
  Gemini session selection there is now also grouped under
  `comm_runtime/session_selection_runtime/`, separating project-scope
  checks, preferred-session adoption, and scan policy so
  `session_selection.py` stays as the stable facade
  Gemini polling there is now further split between the read loop and
  reply-change detection helpers so `comm_runtime/polling.py` remains a
  stable facade
  Gemini polling read-loop state there is now also grouped under
  `comm_runtime/polling_loop_runtime/`, separating loop cursor state,
  timeout handling, and main read orchestration so `polling_loop.py`
  stays as the stable facade
  Gemini active execution start/resume wiring, ready-state waits,
  hook-artifact preference, and snapshot polling now live under
  `provider_backends/gemini/execution_runtime/`, leaving
  `gemini/execution.py` as the adapter facade and stable monkeypatch
  surface for execution tests
  Gemini execution polling there is now also grouped under
  `provider_backends/gemini/execution_runtime/polling_runtime/`,
  separating hook-artifact reads, reply cleanup, and snapshot poll
  orchestration so `execution_runtime/polling.py` stays as the stable
  facade and hook-injection surface
  Gemini project-session file lookup, pane recovery, and session-binding
  persistence now also live under
  `provider_backends/gemini/session_runtime/`, leaving
  `gemini/session.py` as the stable session facade
  Claude project-session selection, JSONL reader polling, subagent log
  handling, log-entry parsing, and session/registry binding support are
  now grouped under `provider_backends/claude/comm_runtime/`, while
  `claude/comm.py` is reduced to the stable top-level facade and
  `ClaudeCommunicator`/`ClaudeLogReader` class bodies now live in
  runtime-local facade modules there; shared path-selection helpers stay
  under `claude/registry_support/`
  Claude reader internals are now further separated there into session
  selection, incremental JSONL I/O, conversation extraction, subagent
  log handling, and polling modules so `comm_runtime/log_reader.py`
  stays as a thin import surface instead of a monolith
  Claude polling read loops there are now also grouped under
  `comm_runtime/polling_runtime/`, separating session wait loops from
  incremental entry/event/message shaping so `polling.py` stays as the
  stable reader facade
  Claude communicator internals there are now also grouped under
  `comm_runtime/communicator_runtime/`, separating session-state setup,
  log-reader binding, registry publication, and ask/ping flows so
  `communicator.py` stays as the stable import facade
  Claude session-selection there is now further grouped under
  `comm_runtime/session_selection_runtime/`, separating reader setup,
  project membership, sessions-index resolution, and scan fallback so
  `session_selection.py` stays as the stable facade
  Claude structured entry/content parsing there is now also grouped
  under `comm_runtime/parsing_runtime/`, separating content-text
  extraction, entry-type message extraction, and structured-event
  shaping so `parsing.py` stays as the stable facade
  Claude active execution start/poll/resume helpers are now grouped
  under `provider_backends/claude/execution_runtime/`, leaving
  `claude/execution.py` as the adapter-facing facade and stable
  monkeypatch surface for execution tests
  Claude execution poll-state updates there are now further grouped
  under `execution_runtime/state_machine_runtime/`, separating poll
  state, assistant/system event handling, and finalization so
  `state_machine.py` stays as the stable facade
  Claude session resolution now lives under
  `provider_backends/claude/resolver_runtime/`, splitting registry
  record expansion, project-path lookup, and final fallback selection so
  `claude/resolver.py` stays as the stable facade
  Claude project-session model, load/fallback selection, and key
  derivation now also live under `provider_backends/claude/session_runtime/`,
  leaving `claude/session.py` as the stable session facade instead of
  mixing model methods with instance-scoped loading and resolver fallback
  Claude session-registry state, direct session-file update helpers, and
  log/sessions-index watcher callbacks are now grouped under
  `provider_backends/claude/registry_runtime/`, leaving
  `claude/registry.py` as the stable facade while registry settings,
  askd-log bridging, singleton access, and monitor orchestration are
  now separated from the runtime implementation modules there;
  session-cache reload logic, monitor-loop checks, and watcher lifecycle
  management are now separated into dedicated runtime modules there
  Claude registry event handling there is now also grouped under
  `registry_runtime/events_runtime/`, separating global log discovery,
  project-watcher log handling, and sessions-index application so
  `events.py` stays as the stable event facade
  Claude registry monitor lifecycle, session refresh sweeps, and
  per-session bind refresh checks are now also grouped under
  `registry_runtime/monitoring_runtime/`, leaving `monitoring.py` as the
  stable monitor facade instead of another mixed loop/checking file
  Claude registry log-discovery helpers are now further grouped under
  `provider_backends/claude/registry_support/logs_runtime/`, separating
  env parsing, sessions-index reads, log metadata reads, binding refresh
  policy, and log discovery so `registry_support/logs.py` stays as the
  stable facade
  Claude registry project-path candidate enumeration and path
  normalization there are now also grouped under
  `provider_backends/claude/registry_support/pathing_runtime/`, leaving
  `registry_support/pathing.py` as the stable facade over shared path
  helpers instead of mixing candidate selection, path matching, and
  session work-dir repair in one file
  OpenCode session-file/runtime wiring and reader-support helpers now
  live under `provider_backends/opencode/runtime/`, leaving
  `opencode/comm.py` more focused on communicator orchestration while
  storage-backed session selection, message/part reads, polling, and
  cancel-detection helpers live in that runtime package
  OpenCode storage-reader internals are now further separated there into
  session lookup, message/part readers, and incremental state-capture
  modules so `runtime/storage_reader.py` remains a stable facade instead
  of accumulating all storage concerns directly
  OpenCode polling there is now further split between reply polling,
  conversation views, and cancel tracking so `runtime/polling.py`
  remains a stable facade instead of holding all live-read behavior
  OpenCode cancel tracking there is now further grouped under
  `runtime/cancel_tracking_runtime/`, separating aborted-assistant
  matching from log-cursor monitoring so `cancel_tracking.py` stays as a
  stable facade instead of another mixed live-state file
  OpenCode communicator initialization, health checks, and send/wait
  flows now also live there so `opencode/comm.py` stays as the stable
  facade exposing `OpenCodeLogReader` and `OpenCodeCommunicator`
  OpenCode active execution start/poll wiring now also lives under
  `provider_backends/opencode/execution_runtime/`, leaving
  `opencode/execution.py` as the stable adapter facade while
  start-flow setup, state/session helpers, and polling stay separated in
  runtime-local modules
  OpenCode project-session lookup, pane recovery, and storage-binding
  persistence now also live under
  `provider_backends/opencode/session_runtime/`, leaving
  `opencode/session.py` as the stable session facade
  Droid log parsing, session discovery, and binding/registry support now
  live under `provider_backends/droid/comm_runtime/`, leaving
  `droid/comm.py` more focused on reader and communicator orchestration
  Droid session scanning/incremental JSONL reads now live under
  `provider_backends/droid/comm_runtime/log_reader.py`, while watchdog
  startup and session-binding callbacks live under
  `provider_backends/droid/comm_runtime/watchdog.py`
  Droid reader internals are now further separated there into session
  selection, content extraction, and incremental polling modules so
  `comm_runtime/log_reader.py` stays as the stable reader facade instead
  of holding all reader behavior directly
  Droid parsing helpers there are now also grouped under
  `comm_runtime/parsing_runtime/`, separating path matching,
  session-start reads, and message-content extraction so `parsing.py`
  stays as the stable facade
  Droid active execution start/poll wiring now also lives under
  `provider_backends/droid/execution_runtime/`, leaving
  `droid/execution.py` as the stable adapter facade while start-flow
  setup, state/session helpers, and polling stay separated in
  runtime-local modules
  Droid session-id/preferred-session state and latest-session selection
  now also live under `provider_backends/droid/comm_runtime/session_selection_runtime/`,
  leaving `session_selection.py` as the stable selection facade
  Droid session-selection helpers there are now further split into
  explicit id lookup, candidate scanning, and final selection modules so
  `session_selection_runtime/lookup.py` no longer accumulates every
  branch of the selection pipeline
  Droid polling read loops and incremental entry/event/message shaping
  there are now also grouped under
  `provider_backends/droid/comm_runtime/polling_runtime/`, leaving
  `polling.py` as the stable reader facade
  Droid project-session lookup, pane recovery, and binding persistence
  now also live under `provider_backends/droid/session_runtime/`,
  leaving `droid/session.py` as the stable session facade
  Qwen, Copilot, and CodeBuddy pane-log parsing and session communicator
  mechanics are now consolidated under
  `provider_backends/pane_log_support/`, leaving each provider's
  `comm.py` as a thin provider-named facade over the shared pane-log
  support layer
- `lib/completion/`
  completion detectors, sources, selectors, and orchestration
  shared enums, dataclass records, and completion utility helpers are
  now grouped under `completion/models_runtime/`, leaving
  `completion/models.py` as the stable import facade for the rest of the
  runtime
  completion record dataclasses there are now further grouped under
  `completion/models_runtime/records_runtime/`, leaving
  `models_runtime/records.py` as the stable re-export facade instead of
  a single flat dataclass pile
- `lib/terminal_runtime/`
  pane-targeted tmux runtime helpers used by v2 paths
  `terminal.py` remains the monkeypatch-stable facade while backend
  selection and layout wiring now live under `terminal_facade/`
  tmux backend orchestration is now further grouped under
  `terminal_runtime/tmux_backend_runtime/`, separating service builders
  and pane/session actions so `tmux_backend.py` stays as the stable
  backend facade instead of a single broad coordination file
  tmux pane lookup, pane metadata reads, and pane mutation helpers are
  now also grouped under `terminal_runtime/tmux_panes_runtime/`, leaving
  `tmux_panes.py` as the stable pane-service facade instead of another
  mixed query/action file
  pane-log root/path selection, trim policy, and stale-log cleanup are
  now also grouped under `terminal_runtime/pane_logs_runtime/`, leaving
  `pane_logs.py` as the stable pane-log facade instead of mixing path
  policy with trim/cleanup details
- `lib/runtime_pid_cleanup/`
  shared project-owned pid collection, procfs evidence reads, path
  ownership matching, pid-file cleanup, and termination helpers used by
  both CLI kill and ccbd stop-flow runtime paths
- `lib/storage/`, `lib/project/`, `lib/workspace/`
  project discovery, path layout, stores, and workspace isolation
- `lib/opencode_runtime/`
  OpenCode storage/log roots, session watching, reply extraction, and
  SQLite-backed session helpers
  path/project-id helpers there are now grouped under
  `opencode_runtime/paths_runtime/`, leaving `paths.py` as the stable
  facade for project-id, path-match, and default-root exports
- `lib/memory/`
  context-transfer parsing, dedupe, formatting, and cross-provider
  session replay helpers
  Claude session resolution, JSONL entry parsing, and session stats
  extraction are now grouped under `memory/session_parser_runtime/`,
  leaving `memory/session_parser.py` as the parser facade
  provider-specific transfer extraction and save/send helpers now live
  under `memory/transfer_runtime/`, leaving `memory/transfer.py` as the
  orchestration facade
  auto-transfer matching, state capture, worker execution, and save/send
  service coordination are now further grouped under
  `memory/transfer_runtime/auto_transfer_runtime/`, leaving
  `transfer_runtime/auto_transfer.py` as the stable auto-transfer facade
  instead of a single mixed replay file
  provider-specific transfer extractors there are now further grouped
  under `memory/transfer_runtime/providers_runtime/`, leaving
  `transfer_runtime/providers.py` as the stable extractor facade instead
  of a flat multi-provider branch file
- `lib/pane_registry_runtime/`
  registry lookup/write helpers for provider pane/session discovery;
  top-level `pane_registry.py` remains compatibility-only
  registry file IO, debug output, path matching, and provider-entry
  liveness there are now grouped under
  `pane_registry_runtime/common_runtime/`, leaving `common.py` as the
  stable registry helper facade instead of a mixed branch-heavy helper
- `lib/web/`
  FastAPI dashboard/runtime helpers now bind explicitly to one resolved
  project root instead of assuming a global daemon context
  route-specific daemon/provider status logic is now grouped under
  `web/route_support/`, so route modules stay API-oriented
  mail route schemas, hook/service helpers, and daemon-control helpers
  are now grouped under `web/route_support/mail/`, leaving
  `web/routes/mail.py` as a route-only facade

### Still co-located but not part of the clean core

- `claude_skills/`, `codex_skills/`, `droid_skills/`
  provider-specific prompt/skill assets
- `bin/`
  legacy provider wrappers plus current helper scripts
- `mcp/ccb-delegation/`
  stdio MCP compatibility server; schema, tool-call handling, and
  JSON-RPC protocol helpers are now split into local runtime helper
  modules so `server.py` stays as the entry facade

## Current File-System Reading

The repo is materially cleaner than before, but still has three obvious
shape issues:

1. The root directory mixes runtime code, provider scripts, prompt
   assets, long-lived design docs, and generated analysis artifacts.
2. The active runtime is modular, but launcher bootstrap and terminal
   orchestration are still dense compared with the rest of the runtime.
3. Tests are broad and valuable, but blackbox coverage is concentrated in
   a single giant file: `test/test_v2_phase2_entrypoint.py`.

## Static Hotspots

Cached `.architec` outputs now report a still-weak but structurally
cleaner baseline:

- overall score: `45.04`
- governance overall: `29.38`
- structure: `60.70`
- largest debt dimensions: `cyclomatic_complexity`, `governance`, `wide_component`

Top cached hotspots:

1. `lib/ccbd/client_runtime/resolution.py`
2. `lib/ccbd/runtime.py`
3. `lib/ccbd/services/dispatcher_runtime/lifecycle_start_runtime/recovery.py`
4. `lib/ccbd/services/dispatcher_runtime/restore.py`
5. `lib/ccbd/services/runtime_runtime/restore.py`

The latest hotspot rounds retired `lib/ccbd/keeper.py`,
`lib/agents/config_loader_runtime/io.py`,
`lib/provider_backends/claude/registry_support/pathing.py`,
`lib/provider_backends/claude/session.py`, and
`lib/pane_registry_runtime/common.py` from the current top-five list.
At this point the remaining drag is concentrated in live `ccbd`
branching paths, not missing package boundaries.

## Largest Remaining Structural Debt

Based on the current tree and local scans, the next cleanup priority is:

1. Converge repeated execution/runtime semantics across
   `lib/provider_backends/*/execution.py`, especially where providers
   still duplicate hook ordering, restore decisions, and active-session
   guards around the shared execution contract; much of this is now
   moved into provider-local `execution_runtime/` packages, but the
   remaining duplication should be watched before it re-accumulates.
2. Refactor the new cyclomatic hotspots before they re-accumulate
   branch debt, especially
   `lib/ccbd/client_runtime/resolution.py`,
   `lib/ccbd/runtime.py`,
   `lib/ccbd/services/dispatcher_runtime/lifecycle_start_runtime/recovery.py`,
   `lib/ccbd/services/dispatcher_runtime/restore.py`, and
   `lib/ccbd/services/runtime_runtime/restore.py`.
3. Keep the remaining large provider/runtime modules under control so
   new orchestration work does not recreate another flat choke point,
   especially in `lib/terminal_runtime/tmux_backend.py`,
   `lib/opencode_runtime/paths_runtime/`, and any new runtime-local
   packages created under terminal management.
4. Watch the new `agents/config_loader_runtime/`,
   `agents/config_loader_runtime/io_runtime/`,
   `agents/config_loader_runtime/parsing_runtime/`,
   `ccbd/keeper_runtime/`, `cli/services/daemon_runtime/`,
   `pane_registry_runtime/common_runtime/`,
   `provider_backends/claude/session_runtime/`,
   `provider_backends/claude/registry_support/pathing_runtime/`,
   `askd/services/dispatcher_runtime/`, and
   `completion/models_runtime/records_runtime/` packages for
   second-order hotspots; the same applies now to
   `cli/kill_runtime/`, `cli/services/kill_runtime/`,
   `askd/models_runtime/`, `askd/adapters/codex_runtime/`,
   `provider_execution/active_runtime/`,
   `terminal_runtime/tmux_backend_runtime/`,
   `terminal_runtime/tmux_panes_runtime/`,
   `provider_backends/codex/comm_runtime/binding_update_runtime/`,
   `provider_backends/codex/comm_runtime/polling_runtime/`,
   `provider_backends/codex/execution_runtime/state_machine_runtime/`,
   `provider_backends/claude/registry_runtime/`,
   `provider_backends/claude/registry_runtime/events_runtime/`,
   `provider_backends/claude/registry_support/logs_runtime/`,
   `provider_backends/claude/comm_runtime/communicator_runtime/`,
   `provider_backends/claude/comm_runtime/parsing_runtime/`,
   `provider_backends/claude/comm_runtime/session_selection_runtime/`,
   `provider_backends/claude/execution_runtime/state_machine_runtime/`,
   `provider_backends/gemini/comm_runtime/binding_update_runtime/`,
   `provider_backends/gemini/comm_runtime/communicator_runtime/`,
   `provider_backends/gemini/comm_runtime/session_selection_runtime/`,
   and `provider_backends/gemini/comm_runtime/polling_loop_runtime/`,
   `provider_backends/droid/comm_runtime/parsing_runtime/`,
   `provider_backends/opencode/runtime/cancel_tracking_runtime/`,
   `provider_backends/droid/execution_runtime/`,
   `provider_backends/opencode/execution_runtime/`,
   `opencode_runtime/paths_runtime/`. If new policy, recovery, or
   serialization logic lands there, split by domain before those runtime
   packages start re-accumulating mixed responsibilities.
5. Keep the newly thin top-level facades stable; if more
   communication-layer cleanup is needed, prefer splitting runtime-local
   helper modules instead of re-growing `provider_backends/*/comm.py`.
6. Separate historical docs from current baseline docs so readers do not
   confuse old migration notes with the current runtime structure.

## Practical Navigation Guide

If you are changing agent-first runtime behavior, start here:

- `ccb`
- `lib/cli/phase2.py`
- `lib/cli/services/`
- `lib/askd/app.py`
- `lib/askd/services/`
- `lib/provider_execution/service.py`
- `lib/provider_execution/registry.py`
- `lib/provider_backends/<provider>/`

If you are changing startup and pane orchestration, start here:

- `ccb`
- `lib/cli/start.py`
- `lib/launcher/`
- `lib/launcher/app_bootstrap.py`
- `lib/terminal.py`
- `lib/terminal_runtime/`

If you are changing persistence or project binding, start here:

- `lib/project/`
- `lib/storage/`
- `lib/workspace/`
- `lib/pane_registry_runtime/`
- `lib/pane_registry.py`
- `lib/session_utils.py`

## Maintenance Rules

- Keep the agent-first path explicit and short.
- Prefer package-local modules over reintroducing giant top-level helper
  files.
- When a module becomes part of the stable package surface, export it
  explicitly from the package `__init__.py`.
- Keep generated artifacts and caches out of the repo root and out of git
  tracking.
