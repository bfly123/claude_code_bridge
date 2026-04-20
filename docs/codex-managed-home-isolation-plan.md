# Codex Managed Home Isolation Plan

## 1. Purpose

This plan defines the implementation path for changing managed Codex isolation
from root-level session isolation to agent-scoped home-level isolation.

The authority contract is
[docs/codex-session-isolation-contract.md](/home/bfly/yunwei/ccb_source/docs/codex-session-isolation-contract.md).
This plan explains how to make the code converge on that contract without
introducing a global-log fallback or another compatibility side path.

## 2. Confirmed Failure

Observed black-box failure:

- workspace: `/home/bfly/yunwei/test_ccb`
- provider: real `codex-cli 0.121.0`
- scenario: `agent1` asks `agent2`
- job: `job_d06cdffcf34a`
- visible provider result: `agent2` answered `2`
- `ccb` execution state: still running because no managed Codex log was bound

Critical evidence:

- `.ccb/ccbd/executions/job_d06cdffcf34a.json`
  - `log_path: null`
  - `session_path: ""`
  - `anchor_seen: false`
- `.ccb/.codex-agent2-session`
  - had `codex_session_root`
  - did not have a bound `codex_session_id` or `codex_session_path`
- `.ccb/agents/agent2/provider-state/codex/home/sessions/`
  - did not receive the real Codex log
- real log was written under the caller-global Codex home:
  - `/home/bfly/.codex/sessions/2026/04/19/rollout-2026-04-19T20-01-07-019da59d-ac36-7932-99ab-2b6801e160af.jsonl`
  - contained `CCB_REQ_ID: job_d06cdffcf34a`
  - contained final answer `2`

Minimal CLI probe confirmed the provider behavior:

- `CODEX_SESSION_ROOT` alone did not cause Codex to write under that root
- `CODEX_HOME` plus `CODEX_SESSION_ROOT` did cause Codex to write under the isolated home

Therefore the failing layer is not mailbox dispatch. The failing layer is the
managed Codex startup and completion boundary.

## 3. Architectural Decision

The managed isolation unit is `CODEX_HOME`, not `CODEX_SESSION_ROOT`.

For every configured `ccb`-managed Codex agent:

- the canonical managed home is `.ccb/agents/<agent>/provider-state/codex/home/`
- the canonical managed session root is `.ccb/agents/<agent>/provider-state/codex/home/sessions/`
- startup must set both `CODEX_HOME` and `CODEX_SESSION_ROOT`
- readers, watchdogs, binding updates, and diagnostics must stay inside that home boundary

This is a boundary change, not a reader fallback.

Rejected fixes:

- scan global `~/.codex/sessions` when no managed log appears
- bind by `work_dir` across multiple configured agents
- adopt a manual Codex conversation just because it contains a `CCB_REQ_ID`
- keep root-only managed sessions as a long-term alternate mode

Those approaches hide the provider-state leak and reintroduce cross-agent
conversation coupling.

## 4. Target State Model

### 4.1 Authority

The authority order for managed Codex is:

1. configured agent identity from `.ccb/ccb.config`
2. `codex_home`
3. `codex_session_root`, derived as `codex_home/sessions`
4. `codex_session_id`
5. `codex_session_path`

`work_dir` is only a prompt execution context and an optional filter inside the
managed home. It is not session identity.

### 4.2 Storage

Canonical layout:

```text
.ccb/
  agents/
    <agent>/
      provider-runtime/
        codex/
          bridge.pid
          bridge.stdout.log
          bridge.stderr.log
          completion/
      provider-state/
        codex/
          home/
            config.toml
            auth.json
            sessions/
              YYYY/MM/DD/rollout-*.jsonl
```

Project session payloads must persist:

- `codex_home`
- `codex_session_root`
- `codex_session_id` after binding
- `codex_session_path` after binding

`auth.json` is a projected credential file. It is not diagnostic export content.

### 4.3 Restart And Resume

Normal restart semantics:

- `ccb_session_id` may change
- `codex_home` must remain stable for the agent
- `codex_session_root` must remain stable and equal `codex_home/sessions`
- `codex_session_id` and `codex_session_path` must be reused when restore is enabled and the bound path is inside the managed home

Fresh reset semantics:

- `ccb -n` is destructive project reset
- the first post-reset startup must force `restore=false`
- old global or project-local Codex conversations must not be silently resumed

## 5. Implementation Workstreams

### Phase A: Path And Layout Authority

Primary files:

- `lib/provider_backends/codex/launcher_runtime/command_runtime/home.py`
- `lib/provider_backends/codex/launcher_runtime/session_paths.py`
- `lib/storage/paths_agents.py`

Required changes:

- make `managed_codex_home(runtime_dir)` the default path, not a fallback used only for invalid source config
- derive `codex_session_root` from `codex_home / "sessions"`
- remove the default `codex_home=None` path for managed Codex launches
- keep provider-profile `runtime_home` only as an explicit override after uniqueness validation
- add one canonical helper for the managed home path so launch, binding, diagnostics, and tests do not duplicate path derivation

Exit criteria:

- a new managed Codex launch always has a concrete private `codex_home`
- `codex_session_root` is never independently selected for new launches

### Phase B: Home Preparation

Primary files:

- `lib/provider_backends/codex/launcher_runtime/command_runtime/home.py`
- provider-profile loading code that feeds Codex launch

Required changes:

- create `home/` and `home/sessions/` before launch
- project non-secret config required by Codex into `home/config.toml`
- project credentials such as `auth.json` only when required for provider authentication
- never treat copied config or credentials as conversation authority
- report preparation failures as startup/degraded diagnostics rather than falling back to global `~/.codex`

Exit criteria:

- Codex can authenticate from the private home
- a missing or malformed source config cannot force conversation state back into global home

### Phase C: Launch Environment And Payload

Primary files:

- `lib/provider_backends/codex/launcher_runtime/command_runtime/service.py`
- `lib/provider_backends/codex/launcher.py`
- `lib/provider_backends/codex/session_runtime/model.py`

Required changes:

- always export `CODEX_HOME=<managed-home>`
- always export `CODEX_SESSION_ROOT=<managed-home>/sessions`
- persist both values in the session payload
- make `codex_home` mandatory in the in-memory project-session model for managed launches
- keep `codex_session_root` as derived persisted metadata for reader compatibility and diagnostics

Exit criteria:

- pane command, bridge process env, session payload, and runtime state agree on the same private home

### Phase D: Binding And Reading Boundaries

Primary files:

- `lib/provider_backends/codex/execution.py`
- `lib/provider_backends/codex/execution_runtime/start.py`
- `lib/provider_backends/codex/comm_runtime/log_reader_facade.py`
- `lib/provider_backends/codex/comm_runtime/session_selection_runtime/`
- `lib/provider_backends/codex/comm_runtime/polling_runtime/`
- `lib/provider_backends/codex/bridge_runtime/binding_runtime.py`
- `lib/provider_backends/codex/bridge_runtime/env.py`

Required changes:

- construct `CodexLogReader` from `codex_home/sessions`
- verify preferred and bound log paths are under the managed home
- use `work_dir` only to choose among logs inside the managed home
- disable workspace-follow behavior as a cross-home adoption mechanism
- make watchdog initial binding accept only logs under the managed home
- make an out-of-home request anchor a diagnostic event, not a completion source

Exit criteria:

- `agent1` and `agent2` can share one `work_dir` without sharing logs
- a manual `codex` command in the same directory cannot be adopted by any managed agent
- completion polling fails explicitly when Codex writes outside the managed home

### Phase E: Legacy Migration

Primary files:

- `lib/provider_backends/codex/launcher_runtime/command_runtime/home.py`
- `lib/provider_backends/codex/comm_runtime/session_runtime_runtime/loading.py`
- session payload update helpers under `lib/provider_backends/codex/`

Required changes:

- classify old payloads that have `codex_session_root` but no `codex_home` as legacy root-only
- if the root is project-local managed state, migrate into the canonical `home/sessions/` layout and rewrite authority
- if the root is global `~/.codex/sessions` or any non-managed external path, refuse silent adoption and surface a migration diagnostic
- keep explicit future import/repair as a separate user action, not part of normal startup

Exit criteria:

- old project-local managed sessions can resume after one migration
- leaked global sessions are not silently imported

### Phase F: Diagnostics And Doctor

Primary files:

- `lib/cli/services/diagnostics_runtime/sources.py`
- doctor/ping surfaces that summarize agent runtime health
- `docs/ccbd-diagnostics-contract.md`

Required changes:

- include non-secret managed home files in support bundles
- exclude `auth.json` and other credential material
- add diagnostics for:
  - `managed_home_empty_after_launch`
  - `codex_wrote_outside_managed_home`
  - `bound_session_outside_managed_home`
  - `legacy_root_only_session_requires_migration`
- include enough path evidence to prove whether a failure is mailbox, provider startup, or log binding

Exit criteria:

- the `/home/bfly/yunwei/test_ccb` failure class points directly to a Codex managed-home violation
- support bundles are sufficient to debug the issue without exporting credentials

## 6. Test Matrix

Unit tests:

- launch command always exports both `CODEX_HOME` and `CODEX_SESSION_ROOT`
- payload always persists `codex_home` and derived `codex_session_root`
- two inplace Codex agents get different homes and roots
- profile runtime homes are validated for uniqueness
- log reader refuses preferred paths outside managed home
- watchdog refuses out-of-home logs
- legacy root-only project-local session migrates once
- legacy root-only global session does not auto-adopt
- diagnostics bundle includes `home/config.toml` and session logs but excludes `home/auth.json`

Black-box tests:

- fresh `ccb -n` project with two inplace Codex agents
- `agent1 ask agent2` completes and binds to `agent2` private home
- manual `codex` conversation in the same project directory does not affect managed completion
- restart `ccb` resumes the same managed `codex_session_id`
- `ccb kill` followed by ordinary `ccb` preserves restart semantics without global adoption
- `ccb -n` after previous global leakage starts fresh and does not resume old global logs

## 7. Non-Drift Rules

- Managed Codex completion must never scan global `~/.codex/sessions` as a fallback.
- Shared `work_dir` must never become managed Codex conversation identity.
- Root-only session state is migration evidence, not steady-state authority.
- `codex_home` is mandatory for new managed Codex launches.
- `codex_session_root` is derived from `codex_home`.
- Contract violations must be diagnostic and visible, not hidden by a best-effort reader fallback.
