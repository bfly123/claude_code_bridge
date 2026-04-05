# Agent-First V2 Clean Core

## Purpose

This document is the clean-cut baseline for `ccb_source` v2.

It supersedes any earlier design notes that assumed long-lived compatibility layers, mixed legacy paths, or dual runtime tracks.

The goal is not to preserve old internal structure. The goal is to produce a smaller, more stable, agent-first core that can grow cleanly.

For the current concrete directory layout, see `docs/current-project-structure.md`.

## Archi Baseline

Latest available `archi --skip-auth` artifacts still point to a very weak whole-repo baseline:

- full score snapshot: `25.2`
- grade: `E`
- release recommendation: `block`

The cached hotspot ordering is still useful even when the exact score lags behind the live worktree:

1. `lib/opencode_comm.py`
2. `lib/claude_comm.py`
3. `lib/terminal.py`
4. `lib/codex_comm.py`
5. `lib/laskd_registry.py`
6. `ccb`

Interpretation:

- the project will not reach `90` by polishing flags or adding compatibility branches
- the only credible path upward is to cut giant files, remove mixed responsibilities, and narrow high-branch provider/runtime boundaries
- `ccb` itself was previously a top debt source and is being reduced in-place by extracting launcher responsibilities into dedicated modules

## Hard Boundaries

The v2 core keeps these rules:

- Agent name is the primary runtime identity.
- Provider is only an agent attribute.
- Each project has one `askd`.
- Project state lives under `.ccb/` only.
- Session lookup only reads `.ccb/<session-file>` while walking upward.
- `ccb` v2 behavior must converge toward a single path: `cli -> askd -> provider_execution -> completion -> storage`.
- `codex`, `claude`, and `gemini` are first-class phase-1 providers.
- Legacy providers may exist, but they must not shape core abstractions.
- The top-level `ccb` entrypoint must try phase2 before any legacy fallback path.

The v2 core explicitly rejects these old patterns:

- `.ccb_config/`
- project-root provider session files like `.codex-session` outside `.ccb/`
- global `compatibility_mode` policy in agent models
- fallback flags leaking into the shared completion model
- tmux session-name / pane-id mixed target semantics as a core runtime contract
- multiple provider-specific daemons as the main architecture
- phase1/phase2 long-term coexistence as the target state

For tmux specifically:

- legacy modules may still call generic terminal methods that accept session-name fallback
- v2 runtime paths must call pane-only helpers and treat `%<pane>` as the only valid tmux runtime target

## Core Model Decisions

### Agent Spec

`AgentSpec` is reduced to fields that affect actual v2 behavior:

- `name`
- `provider`
- `target`
- `workspace_mode`
- `workspace_root`
- `runtime_mode`
- `restore_default`
- `permission_default`
- `queue_policy`
- `startup_args`
- `env`
- `branch_template`
- `labels`
- `description`
- `watch_paths`

Removed from core:

- `compatibility_mode`

Reason:

- completion fallback is not an agent-wide policy knob
- it couples unrelated providers together
- it turns degraded transport behavior into a global configuration surface

### Completion Model

Structured providers and legacy providers are separated by detector family, not by a shared compatibility switch.

Current clean split:

- `codex` -> `protocol_turn`
- `claude` -> `session_boundary`
- `gemini` -> `anchored_session_stability`
- legacy text providers -> `legacy_text_quiet`

Removed from shared completion profile/request context:

- `compatibility_mode`
- `supports_legacy_quiet_fallback`

Reason:

- structured providers should not carry fallback metadata they do not use
- legacy timeout behavior should stay inside the legacy detector implementation
- the shared completion API should describe signal shape, not migration policy

## Path Rules

The only valid project config directory is:

```text
<project>/.ccb/
```

The only valid upward session lookup is:

```text
<ancestor>/.ccb/<session_filename>
```

Rejected lookup paths:

```text
<ancestor>/.ccb_config/<session_filename>
<ancestor>/<session_filename>
```

A small alias may remain in helper code only to keep untouched modules import-safe, but the runtime path is still `.ccb/` only.

## Default Config Policy

Phase-1 default generated agents are now:

- `codex`
- `claude`
- `gemini`

Removed from default generated config:

- `opencode`
- `droid`

Reason:

- defaults should represent the stable core, not every historical adapter
- non-core providers can be added explicitly by the user when needed

## askd Stability Rules

`askd` must be stable under long-running turns and shutdown races.

Current rules:

- heartbeat must not revive an already unmounted lease
- `serve_forever()` must mark the lease unmounted in `finally`
- socket removal alone is not considered sufficient shutdown state
- lease state is the source of truth for mounted/unmounted transition

Operational note:

- when running integration or blackbox tests that launch real pane-backed providers, keep those suites serial
- tmux-backed provider tests can interfere with each other if multiple pytest processes are launched in parallel against the same host session environment

## Entry Point Rules

The top-level `ccb` script is being reduced to a phase2-first dispatcher.

Current clean-core behavior:

- `ccb` tries `maybe_handle_phase2()` first
- `ccb config validate` is handled by phase2, not by a phase1-only pre-dispatch path
- legacy branches may still exist for non-v2 commands, but they are no longer the first routing decision for v2 projects
- non-phase2 CLI handling is isolated under `lib/cli/router.py` so the top-level script only wires handlers
- phase2 output rendering is being moved under `lib/cli/render.py` so `phase2.py` stays a control layer instead of a print-heavy mixed module

Current target file roles:

- `ccb`: top-level route selection and legacy handler wiring only
- `lib/cli/phase2.py`: phase2 command parsing, context build, service dispatch
- `lib/cli/render.py`: text output formatting for phase2 commands
- `lib/cli/router.py`: non-phase2 auxiliary / management / start argument routing
- `lib/cli/start.py`: project anchor checks, provider parsing, default start selection
- `lib/cli/management.py`: management command implementations (`version/update/uninstall/reinstall`)
- `lib/cli/kill.py`: kill command implementation (session cleanup, daemon shutdown, zombie cleanup)
- `lib/cli/auxiliary.py`: auxiliary command implementations (`droid`, `mail`)
- `lib/launcher/daemon_manager.py`: launcher-scoped provider daemon boot, askd ownership checks, watchdog lifecycle
- `lib/launcher/session_store.py`: launcher-scoped project session persistence, Claude local session backfill, session inactivation helpers

## Terminal Rules

`terminal.py` still contains old generic methods because legacy code is co-located in the repo.

The clean v2 rule is narrower:

- `provider_execution/*` must use runtime-target helpers, not direct `backend.send_text()` / `backend.is_alive()` calls
- `TmuxBackend.send_text_to_pane()` is the v2 submit path for tmux-backed agents
- `TmuxBackend.is_tmux_pane_alive()` is the v2 liveness path for tmux-backed agents
- `TmuxBackend.kill_tmux_pane()` and `TmuxBackend.activate_tmux_pane()` are the v2 pane-management primitives
- session-name fallback remains isolated to generic legacy methods only

## Phase-1 Test Contract

The minimum regression set for clean-core changes is:

```bash
python -m pytest -q \
  test/test_v2_config_loader.py \
  test/test_v2_completion_models.py \
  test/test_v2_completion_detectors.py \
  test/test_v2_completion_registry.py \
  test/test_v2_policy.py \
  test/test_v2_agent_store.py \
  test/test_v2_runtime_launch.py \
  test/test_v2_workspace_manager.py \
  test/test_session_utils.py
```

askd lifecycle and blackbox checks:

```bash
python -m pytest -q test/test_v2_askd_mount_ownership.py
python -m pytest -q test/test_v2_askd_dispatcher.py test/test_v2_phase1_entrypoint.py
python -m pytest -q test/test_v2_phase2_entrypoint.py -k "ccb_v2_project_lifecycle or fake_legacy_provider_degraded_done_marker_completion or two_named_codex_agents_concurrent_ask_isolated"
python -m pytest -q test/test_tmux_backend.py test/test_v2_runtime_isolation.py test/test_v2_execution_service.py -k "strict or runtime_isolation or codex_adapter_prefers_strict_tmux_target_helpers"
python -m pytest -q test/test_v2_cli_render.py test/test_v2_cli_router.py
python -m pytest -q test/test_v2_cli_management.py test/test_v2_cli_kill.py test/test_v2_cli_auxiliary.py test/test_v2_cli_start.py
```

## Next Cleanups

The next structural deletions should happen in this order:

1. Continue shrinking `ccb` by extracting the remaining `AILauncher` clusters, with daemon/watchdog and session persistence already moved out; next is provider start-command construction and pane launch orchestration.
2. Split `lib/terminal.py` into backend-specific runtime modules so pane lifecycle, input injection, and layout control are no longer coupled in one file.
3. Continue collapsing communication logic into `lib/provider_backends/*` so backend-specific log scanning, session resolution, and completion helpers no longer live in giant top-level files.
4. Remove remaining `.ccb_config` and root-session fallback assumptions from co-located helper modules.
5. Collapse `askd/adapters/*` further out of the main runtime path so `provider_execution/*` is the only execution path for agent-first flows.
6. Continue shrinking the top-level `ccb` file by extracting remaining `AILauncher` clusters, especially provider start-command construction and pane launch orchestration.
7. Push non-core providers behind explicit opt-in registration instead of default catalog pressure.

## Acceptance Criteria

The clean-core baseline is considered healthy when:

- v2 config no longer accepts `compatibility_mode`
- generated config only contains the phase-1 core providers
- session lookup only resolves `.ccb/` files
- codex/claude/gemini completion paths do not depend on text markers or quiet fallback
- v2 provider execution does not directly call tmux generic `send_text` / `is_alive` APIs
- legacy timeout behavior is isolated to legacy detector code only
- askd shutdown leaves the lease in `unmounted` state even under concurrent ticks
