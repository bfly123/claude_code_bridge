# Codex Session Isolation Contract

## 1. Purpose

This document defines the non-drifting contract for `ccb`-managed Codex home and session isolation.

It is the authoritative design anchor for:

- `codex` startup environment under `ccb`
- agent-scoped Codex provider state layout
- Codex home and session root selection and persistence
- Codex bootstrap binding vs bound-session reading
- isolation from non-`ccb` Codex conversations

This document complements, but does not replace, the project startup contract in
[docs/ccbd-startup-supervision-contract.md](/home/bfly/yunwei/ccb_source/docs/ccbd-startup-supervision-contract.md).

Detailed implementation sequencing lives in
[docs/codex-managed-home-isolation-plan.md](/home/bfly/yunwei/ccb_source/docs/codex-managed-home-isolation-plan.md).

## 2. Identity Model

`ccb` must treat these identities as distinct:

- `agent identity`
  - project anchor + logical agent name + provider
- `runtime generation`
  - one launch generation, currently represented by `ccb_session_id`
- `provider conversation identity`
  - the concrete Codex conversation, represented by `codex_session_id`

`work_dir` is context only. It must not be treated as the primary identity for a managed Codex agent.

`CODEX_HOME` is the managed provider-state boundary. `CODEX_SESSION_ROOT`
is derived state inside that boundary, not an independent isolation authority.

Verified operational constraint:

- with `codex-cli 0.121.0`, setting only `CODEX_SESSION_ROOT` is not sufficient to contain Codex conversation logs
- setting an isolated `CODEX_HOME` is required for managed Codex logs and session state to remain under `ccb` authority

## 3. Storage Contract

For a managed Codex agent named `<agent>`:

- runtime artifacts live under:
  - `.ccb/agents/<agent>/provider-runtime/codex/`
- stable provider state lives under:
  - `.ccb/agents/<agent>/provider-state/codex/`

The canonical managed Codex runtime artifact layout includes at minimum:

- `.ccb/agents/<agent>/provider-runtime/codex/completion/`
- `.ccb/agents/<agent>/provider-runtime/codex/bridge.log`

By default, the managed Codex home is:

- `.ccb/agents/<agent>/provider-state/codex/home/`

By default, the managed Codex session root is derived from that home:

- `.ccb/agents/<agent>/provider-state/codex/home/sessions/`

If the effective Codex home is explicitly overridden by a provider profile, the effective session root must still be:

- `<codex_home>/sessions/`

Provider-profile runtime homes are explicit authority only when they preserve the managed isolation contract. Two configured Codex agents must not resolve to the same effective `codex_home` unless a future explicit shared-home feature declares and validates that weaker isolation mode.

The managed session file must persist:

- `codex_home`
- `codex_session_root`
- `codex_session_id` once bound
- `codex_session_path` once bound

These fields are authority for managed Codex runtime recovery.

For new managed launches, `codex_home` is mandatory. A session file without
`codex_home` is legacy evidence that must be migrated or rejected before it can
be used as normal managed authority.

Credential and config projection is not conversation identity. `ccb` may project
the user's source Codex credentials and config into the private managed home so
the provider can authenticate, but projected credential files remain secret
material and must not be exported by diagnostics.

## 4. Startup Contract

When `ccb` starts a managed Codex agent:

- it must explicitly set the effective `CODEX_HOME`
- it must explicitly set the effective `CODEX_SESSION_ROOT`
- it must ensure `CODEX_SESSION_ROOT == CODEX_HOME/sessions`
- it must create the managed home and session root before launching Codex
- it must materialize required Codex config and credential projections into the managed home without treating them as session identity
- it must refresh inheritable Codex config, auth, skills, and commands projections into the managed home on each managed launch so source-home updates become visible after restart
- when API inheritance is enabled, it must pass the current inheritable Codex API environment into the managed Codex process at launch time rather than relying on stale one-time projection state
- it must write the effective `codex_home` and `codex_session_root` into the agent session file
- it must create the canonical runtime `completion/` directory and `bridge.log` before the managed launch is considered bootstrap-ready
- it must not rely on global `~/.codex/sessions` as the default managed session namespace

Profile-provided runtime-home overrides are explicit forward authority only after uniqueness and boundary validation.

Absent such an override, the managed agent-scoped `CODEX_HOME` is the default authority.

Startup must fail clearly or mark the agent degraded when the requested managed
home cannot be prepared. It must not silently fall back to the caller's global
Codex home.

Project control-plane isolation rule:

- `ccb`, keeper, and `ccbd` must not inherit Codex runtime-local session variables from the caller shell
- examples include `CCB_SESSION_ID`, `CCB_SESSION_FILE`, `CCB_CALLER_*`, `CODEX_RUNTIME_DIR`, `CODEX_INPUT_FIFO`, `CODEX_OUTPUT_FIFO`, `CODEX_TERMINAL`, and equivalent runtime markers
- those variables belong only to the managed Codex runtime process that was launched for one agent generation
- a fresh project control-plane subprocess must treat such caller-shell variables as contamination, not startup authority
- only the managed agent session file and managed provider-state under `.ccb/agents/<agent>/provider-state/codex/` may define restore authority for a project-scoped Codex agent

## 5. Binding Contract

Managed Codex session reading has exactly two modes:

- `bootstrap`
  - used when the agent is not yet bound to a concrete Codex conversation
  - may scan for a candidate session only within that agent's own `codex_home/sessions`
  - may use `work_dir` only as a filter inside that managed home
- `bound`
  - used after `codex_session_id` or `codex_session_path` exists
  - must prefer the bound session
  - must verify the bound path remains inside that agent's managed home
  - must not drift to a newer workspace session outside explicit rebinding logic

Binding logic must not use shared `work_dir` as the cross-agent reconciliation key.

Asynchronous binding paths such as log watchdogs must also honor the managed home and must not rebind an already bound managed session to a different Codex conversation only because a newer workspace log appeared.

Managed readers must not widen their search to global `~/.codex/sessions`,
even when they can see a request anchor there. A request anchor observed outside
the managed home is a contract violation or legacy-leak diagnostic, not a
completion source.

Runtime pane reuse is a separate proof obligation from session-file binding:

- a live tmux pane is not sufficient proof that the managed Codex agent is attached to the bound provider conversation
- when `codex_session_id` exists, startup may reuse an existing live pane only if the live provider process identity proves it is running `codex ... resume <codex_session_id>`
- if the live process identity is missing, unknown, or proves a different/non-resume Codex command, startup must reject that pane as reusable evidence and relaunch through the normal managed start command
- the persisted `start_cmd` or `codex_start_cmd` is desired launch authority, not proof that the current pane process was launched with that command
- relaunch after identity mismatch must preserve the agent-scoped `codex_home`, derived `codex_session_root`, and bound `codex_session_id` so ordinary `ccb` restores history while `ccb -n` remains the explicit fresh-start path

Legacy agent-only reuse exception:

- when the project is in an agent-only legacy layout with `cmd` disabled and the instance-scoped session file does not declare a conflicting tmux socket, startup may still reuse that binding even if live Codex identity proof is temporarily unavailable or `unknown`
- that exception does not apply when live identity explicitly proves `mismatch`

## 6. Isolation Contract

By default:

- two `ccb`-managed Codex agents must not share a Codex home
- two `ccb`-managed Codex agents must not share a session root
- two `inplace` Codex agents may share the same `work_dir`, but must still remain isolated
- a non-`ccb` Codex conversation started in the same working directory must not be implicitly adopted by a managed agent

External Codex conversations may only be adopted through an explicit future bind/import flow.

Therefore `ccb` and a manually-run `codex` command in the project directory are
separate worlds:

- the manual command may use the user's normal `~/.codex`
- the managed agent must use its agent-scoped private `CODEX_HOME`
- shared `cwd` or matching request text does not merge their conversations

## 7. Compatibility Contract

To avoid breaking restore for older managed sessions, startup may reuse and
migrate a previously recorded Codex home when it is already persisted in the
agent session authority.

Compatibility reuse is evidence-driven migration support only. New managed launches must write the current explicit `codex_home` and derived `codex_session_root` contract back to authority.

Legacy root-only sessions are not a long-term operating mode:

- if the old root is project-local managed state, startup may relocate or bridge it into the canonical private home and then rewrite authority
- if the old session evidence points to global `~/.codex/sessions` or another non-managed home, normal startup must not silently adopt it
- any import of leaked or external global Codex sessions requires an explicit future repair/import flow

`ccb -n` remains a valid way to rebuild a project with fresh managed homes. The
first post-reset startup must force `restore=false` as defined by the startup
contract, so old provider-global history is not silently reattached.

## 8. Diagnostics Contract

When managed Codex state lives inside the project under `.ccb/agents/<agent>/provider-state/codex/`, diagnostics and support bundles should treat that provider-state tree as project-local evidence.

Diagnostics export should include:

- managed home summary metadata
- managed session-root logs and related project-local session files
- non-secret isolated `config.toml` overlays when present
- explicit contract-violation evidence when Codex writes outside the managed home

Diagnostics export must exclude copied credential files such as `auth.json`.

Runtime diagnostics should distinguish these cases:

- `unbound_waiting_for_managed_log`
- `managed_home_empty_after_launch`
- `codex_wrote_outside_managed_home`
- `bound_session_outside_managed_home`
- `legacy_root_only_session_requires_migration`

These states are diagnosable failures or migrations. They are not permission to
scan global provider history as a fallback.
