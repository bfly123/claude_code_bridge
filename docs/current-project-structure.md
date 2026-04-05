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
  kill-command zombie cleanup, provider session teardown, and daemon
  termination helpers are now grouped under `cli/kill_runtime/`,
  leaving `cli/kill.py` as the stable command facade and monkeypatch
  surface
  CLI install/update/version helpers are now grouped under
  `cli/management_runtime/`, leaving `cli/management.py` as a stable
  facade for management command handlers
  start-time project-config validation, provider parsing, lock reuse,
  and selection helpers are now grouped under `cli/start_runtime/`,
  leaving `cli/start.py` as the stable start helper facade
  runtime launcher pane creation/fallback and session-file writes are
  now grouped under `cli/services/runtime_launch_runtime/`, leaving
  `services/runtime_launch.py` focused on gate checks, launcher
  selection, and monkeypatch-stable wrapper helpers
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
  `agents.config_loader` is now a stable facade over
  `agents/config_loader_runtime/`, with compact config loading, validation,
  default-template rendering, and config-path helpers separated into
  dedicated modules
- `lib/mail/`
  email ingress, routing, polling, sending, and ask-bridge integration
  mail ask submission/context helpers are now grouped under
  `mail/ask_runtime/`, leaving `mail/ask_handler.py` focused on
  message normalization and orchestration instead of mixing context
  persistence, environment assembly, and ask submission details
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
- `lib/provider_core/`
  shared provider manifests, registry surfaces, path/session naming, and
  compatibility glue
  builtin backend assembly and fake-provider backend assembly now live
  under `provider_core/registry_runtime/`, leaving `registry.py`
  focused on the public registry surface and default builder entrypoints
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
  Codex polling read-loop state there is now also grouped under
  `comm_runtime/polling_runtime/`, separating read cursor state,
  line-decoding/match extraction, and log-switch handling so
  `polling.py` stays as the stable facade
  Codex active execution start/resume wiring and protocol polling logic
  are now grouped under `provider_backends/codex/execution_runtime/`,
  leaving `codex/execution.py` as the adapter facade and stable
  monkeypatch surface for execution tests
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
  Codex project-session file lookup, pane self-heal, and log-binding
  persistence now also live under
  `provider_backends/codex/session_runtime/`, leaving `codex/session.py`
  as the stable session facade
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
  Claude communicator internals there are now also grouped under
  `comm_runtime/communicator_runtime/`, separating session-state setup,
  log-reader binding, registry publication, and ask/ping flows so
  `communicator.py` stays as the stable import facade
  Claude session-selection there is now further grouped under
  `comm_runtime/session_selection_runtime/`, separating reader setup,
  project membership, sessions-index resolution, and scan fallback so
  `session_selection.py` stays as the stable facade
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
  Claude session-registry state, direct session-file update helpers, and
  log/sessions-index watcher callbacks are now grouped under
  `provider_backends/claude/registry_runtime/`, leaving
  `claude/registry.py` as the stable facade while registry settings,
  askd-log bridging, singleton access, and monitor orchestration are
  now separated from the runtime implementation modules there;
  session-cache reload logic, monitor-loop checks, and watcher lifecycle
  management are now separated into dedicated runtime modules there
  Claude registry log-discovery helpers are now further grouped under
  `provider_backends/claude/registry_support/logs_runtime/`, separating
  env parsing, sessions-index reads, log metadata reads, binding refresh
  policy, and log discovery so `registry_support/logs.py` stays as the
  stable facade
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
  Droid active execution start/poll wiring now also lives under
  `provider_backends/droid/execution_runtime/`, leaving
  `droid/execution.py` as the stable adapter facade while start-flow
  setup, state/session helpers, and polling stay separated in
  runtime-local modules
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
- `lib/pane_registry_runtime/`
  registry lookup/write helpers for provider pane/session discovery;
  top-level `pane_registry.py` remains compatibility-only
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

Cached `.architec` outputs still report a weak overall baseline:

- overall score: `25.2`
- largest debt dimensions: `complexity`, `code_style`, `file_size`

Top cached hotspots:

1. `lib/opencode_comm.py`
2. `lib/claude_comm.py`
3. `lib/terminal.py`
4. `lib/codex_comm.py`
5. `lib/laskd_registry.py`
6. `lib/gemini_comm.py`
7. `lib/droid_comm.py`
8. `lib/askd/adapters/claude.py`

Some of those top entries have already been retired from the current
main path, so they should be read as debt history plus file-size signal,
not as an exact description of today's live import graph.

## Largest Remaining Structural Debt

Based on the current tree and local scans, the next cleanup priority is:

1. Converge repeated execution/runtime semantics across
   `lib/provider_backends/*/execution.py`, especially where providers
   still duplicate hook ordering, restore decisions, and active-session
   guards around the shared execution contract; much of this is now
   moved into provider-local `execution_runtime/` packages, but the
   remaining duplication should be watched before it re-accumulates.
2. Keep the remaining large provider/runtime modules under control so
   new orchestration work does not recreate another flat choke point,
   especially in `lib/terminal_runtime/tmux_backend.py`,
   `lib/opencode_runtime/paths_runtime/`, and any new runtime-local
   packages created under terminal management.
3. Watch the new `agents/config_loader_runtime/`,
   `askd/services/dispatcher_runtime/`, and
   `completion/models_runtime/records_runtime/` packages for
   second-order hotspots; the same applies now to
   `cli/kill_runtime/`,
   `askd/models_runtime/`, `askd/adapters/codex_runtime/`,
   `provider_execution/active_runtime/`,
   `terminal_runtime/tmux_backend_runtime/`,
   `provider_backends/codex/comm_runtime/binding_update_runtime/`,
   `provider_backends/codex/comm_runtime/polling_runtime/`,
   `provider_backends/codex/execution_runtime/state_machine_runtime/`,
   `provider_backends/claude/registry_runtime/`,
   `provider_backends/claude/registry_support/logs_runtime/`,
   `provider_backends/claude/comm_runtime/communicator_runtime/`,
   `provider_backends/claude/comm_runtime/session_selection_runtime/`,
   `provider_backends/claude/execution_runtime/state_machine_runtime/`,
   `provider_backends/gemini/comm_runtime/binding_update_runtime/`,
   `provider_backends/gemini/comm_runtime/communicator_runtime/`, and
   `provider_backends/gemini/comm_runtime/polling_loop_runtime/`,
   `provider_backends/droid/execution_runtime/`,
   `provider_backends/opencode/execution_runtime/`,
   `opencode_runtime/paths_runtime/`. If new policy, recovery, or
   serialization logic lands there, split by domain before those runtime
   packages start re-accumulating mixed responsibilities.
4. Keep the newly thin top-level facades stable; if more
   communication-layer cleanup is needed, prefer splitting runtime-local
   helper modules instead of re-growing `provider_backends/*/comm.py`.
5. Separate historical docs from current baseline docs so readers do not
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
