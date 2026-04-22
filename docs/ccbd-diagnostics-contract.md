# CCBD Diagnostics Contract

## 1. Purpose

This document defines the non-drifting diagnostics contract for project-scoped startup/shutdown reports, backend logs, and support-bundle export in `ccb_source`.

It is the authoritative design anchor for:

- `.ccb/ccbd/startup-report.json`
- `.ccb/ccbd/shutdown-report.json`
- `.ccb/ccbd/ipc.json`
- `.ccb/ccbd/state.json`
- `.ccb/ccbd/start-policy.json`
- `.ccb/ccbd/lifecycle.jsonl`
- `.ccb/ccbd/heartbeats/<subject-kind>/*.json`
- project-scoped backend log retention under `.ccb/ccbd/`
- `ccb doctor`
- `ccb doctor --bundle`

The repo-local memory file [AGENTS.md](/home/bfly/yunwei/ccb_source/AGENTS.md) must point to this document instead of duplicating the rules.

## 2. Goals

Diagnostics must let another user reproduce backend state and failure context without interactive shell access to the original machine.

That means the diagnostics surface must answer at least:

- what the project anchor was
- which config was active
- whether the backend was mounted, restarted, recovered, or shut down
- which agents were expected, mounted, degraded, or stopped
- what the daemon and keeper most recently logged
- which authority files and event streams existed at the time of export

## 3. Hard Contract

### 3.1 Project Scope

- Diagnostics are scoped to one `.ccb` anchor.
- All project diagnostics records must live under that anchor's `.ccb/ccbd/`, except for provider session files that may live outside the project and are referenced as evidence.
- Diagnostics export must never merge multiple project anchors into one bundle.

### 3.2 Startup Report

Path:

- `.ccb/ccbd/startup-report.json`

The latest startup report must capture the most recent startup-related transaction, including:

- `trigger`
  - at minimum `daemon_boot` or `start_command`
- `status`
  - at minimum `ok` or `failed`
- `generated_at`
- `daemon_generation`
- optional `daemon_started`
  - whether the foreground `ccb` command had to start a new daemon
- `requested_agents`
- `desired_agents`
- `actions_taken`
- `agent_results`
- `inspection`
- optional `failure_reason`

Rules:

- daemon boot must write a startup report
- foreground `start` must overwrite it with the more specific `start_command` report
- startup report write failure must not replace the original startup error with a diagnostics-only error

### 3.3 Shutdown Report

Path:

- `.ccb/ccbd/shutdown-report.json`

The latest shutdown report must capture the most recent shutdown-related transaction, including:

- `trigger`
  - at minimum `shutdown`, `stop_all`, `kill`, or `kill_fallback`
- `status`
- `generated_at`
- `forced`
- `stopped_agents`
- `actions_taken`
- `cleanup_summaries`
- `inspection_after`
- optional `failure_reason`

Rules:

- normal server-side stop/shutdown must write a shutdown report
- CLI fallback kill must also write a shutdown report
- the final persisted shutdown report must reflect post-shutdown state, not an intermediate pre-unmount snapshot

### 3.4 Backend Logs

Project backend logs must remain under `.ccb/ccbd/`:

- `ccbd.stdout.log`
- `ccbd.stderr.log`
- `keeper.stdout.log`
- `keeper.stderr.log`

Rules:

- daemon and keeper must append logs to stable file paths
- diagnostics readers must treat these as evidence, not authority
- large logs may be tailed during export, but the manifest must explicitly mark truncation

### 3.5 Namespace State And Lifecycle

Paths:

- `.ccb/ccbd/ipc.json`
- `.ccb/ccbd/state.json`
- `.ccb/ccbd/start-policy.json`
- `.ccb/ccbd/lifecycle.jsonl`
- `.ccb/ccbd/heartbeats/<subject-kind>/*.json`

Rules:

- `ipc.json` records the latest persisted backend ipc facts such as `ipc_kind`, `ipc_ref`, `backend_family`, `backend_impl`, and latest `updated_at`
- `state.json` records the latest persisted project namespace facts such as `namespace_epoch`, `session_name`, `backend_ref`, `window_id`, `layout_version`, `visible_layout_signature`, and latest lifecycle summary when known
- `start-policy.json` records the persisted project recovery startup policy, including inherited `auto_permission` and forced recovery-restore semantics
- `lifecycle.jsonl` records namespace creation/destruction and later runtime lifecycle events
- `heartbeats/<subject-kind>/*.json` records non-lease heartbeat state for long-lived supervised subjects such as running jobs; these files are diagnostics/evidence, not backend ownership authority
- daemon lease heartbeat and subject heartbeat must remain separate concepts and separate files
- `doctor` and bundle export must include these records when present
- `ping('ccbd')` and `doctor` should surface start-policy summary fields when available
- `ping('ccbd')` and `doctor` must surface namespace summary fields such as epoch, backend family/impl, backend ref, ipc kind/ref, session name, and latest lifecycle event when available
- malformed namespace diagnostics must surface as diagnostics errors, not silently disappear

### 3.6 Doctor Read Path

`ccb doctor` is the best-effort project diagnostics read path.

Rules:

- it must summarize current backend inspection plus latest persisted reports
- it should surface persisted `ipc_kind`, `ipc_ref`, `backend_family`, `backend_impl`, `ipc_state`, `ipc_updated_at`, `job_id`, and `job_owner_pid` when available
- agent binding diagnostics must include namespace binding metadata such as `backend_family`, `backend_impl`, `backend_ref`, legacy `tmux_socket_name` / `tmux_socket_path`, `ipc_kind`, `ipc_ref`, `job_id`, and `job_owner_pid` when known so project-scoped namespace bugs can be diagnosed from logs alone
- it must not crash only because one diagnostics artifact is missing or malformed
- malformed diagnostics files must surface as diagnostics errors, not silent omission

### 3.7 Support Bundle Export

Command:

- `ccb doctor --bundle`

Default output location:

- `.ccb/ccbd/support/<bundle-id>.tar.gz`

The support bundle must include:

- a manifest
- a generated doctor snapshot
- current project config from `.ccb/ccb.config`
- latest lifecycle reports
- backend authority files such as lease, keeper, shutdown intent, ipc state, and namespace state when present
- backend recovery policy authority such as `start-policy.json` when present
- persisted non-lease heartbeat state under `.ccb/ccbd/heartbeats/` when present
- recent backend event streams such as supervision, namespace lifecycle, and cleanup history
- backend stdout/stderr logs
- per-agent runtime authority and recent agent/provider logs
- relevant external session files when discoverable from runtime authority

Rules:

- bundle export must be best-effort and continue when some files are missing or malformed
- manifest rows must include original source path, archive path, inclusion status, and truncation status
- bundle export must not require the backend to be healthy
- bundle export must be project-local and deterministic enough for support usage

### 3.8 Keeper Child Reaping

The keeper may directly spawn `ccbd`, but it must reap exited direct children.

Rule:

- a crashed or killed `ccbd` process must not remain visible as an unreaped zombie just because keeper is still alive

## 4. Operational Workflow

Recommended support workflow:

1. reproduce the issue in the project anchor
2. run `ccb doctor`
3. run `ccb doctor --bundle`
4. send the generated tarball

The bundle is the transport unit. The reports inside it are the authoritative timeline.

## 5. Update Discipline

- If startup or shutdown reporting changes, update this document in the same patch.
- If `doctor` or bundle contents change materially, update this document in the same patch.
- Use [docs/ccbd-manual-test-issue-log.md](/home/bfly/yunwei/ccb_source/docs/ccbd-manual-test-issue-log.md) for concrete incidents and repro findings.
