# Gemini Session Isolation Contract

## 1. Purpose

This document defines the non-drifting contract for `ccb`-managed Gemini home
and session isolation.

It is the authoritative design anchor for:

- `gemini` startup environment under `ccb`
- agent-scoped Gemini provider state layout
- Gemini home and temp-root persistence
- Gemini bootstrap binding vs bound-session reading
- isolation from non-`ccb` Gemini conversations

This document complements, but does not replace, the project startup contract in
[docs/ccbd-startup-supervision-contract.md](/home/bfly/yunwei/ccb_source/docs/ccbd-startup-supervision-contract.md).

## 2. Identity Model

`ccb` must treat these identities as distinct:

- `agent identity`
  - project anchor + logical agent name + provider
- `runtime generation`
  - one launch generation, currently represented by `ccb_session_id`
- `provider conversation identity`
  - the concrete Gemini conversation, represented by `gemini_session_id`

`work_dir` is context only. It must not be treated as the primary identity for a
managed Gemini agent.

The effective managed `HOME` is the provider-state boundary for Gemini under
`ccb`. The effective managed Gemini temp root is derived state inside that
boundary, not an independent authority.

Operational constraint:

- Gemini CLI reads both user-level `~/.gemini/...` state and project-level
  `.gemini/...` state
- managed isolation therefore requires a private `HOME` projection plus an
  explicit managed `GEMINI_ROOT`
- startup must not rely on project-level `.gemini/settings.json` as managed
  authority

## 3. Storage Contract

For a managed Gemini agent named `<agent>`:

- runtime artifacts live under:
  - `.ccb/agents/<agent>/provider-runtime/gemini/`
- stable provider state lives under:
  - `.ccb/agents/<agent>/provider-state/gemini/`

By default, the managed Gemini home is:

- `.ccb/agents/<agent>/provider-state/gemini/home/`

Inside that home, the managed Gemini state is:

- `.ccb/agents/<agent>/provider-state/gemini/home/.gemini/settings.json`
- `.ccb/agents/<agent>/provider-state/gemini/home/.gemini/trustedFolders.json`
- `.ccb/agents/<agent>/provider-state/gemini/home/.gemini/tmp/`

If the effective Gemini home is explicitly overridden by a provider profile, the
effective temp root must still be derived from that home:

- `<gemini_home>/.gemini/tmp/`

Two configured Gemini agents must not resolve to the same effective
`gemini_home` unless a future explicit shared-home mode declares and validates
that weaker isolation contract.

The managed session file must persist:

- `gemini_home`
- `gemini_root`
- `gemini_session_id` once bound
- `gemini_session_path` once bound

These fields are authority for managed Gemini runtime recovery.

## 4. Startup Contract

When `ccb` starts a managed Gemini agent:

- it must explicitly set the effective `HOME`
- it must explicitly set the effective `GEMINI_ROOT`
- it must ensure `GEMINI_ROOT == <gemini_home>/.gemini/tmp`
- it must create the managed home and managed temp root before launching Gemini
- it must materialize required Gemini auth/config projections into the managed
  home without treating them as conversation identity
- managed Gemini home materialization is part of startup preparation, before
  hook/trust installation and before launcher command assembly
- managed `settings.json` projection must treat inherited system settings as the
  baseline and preserve managed runtime sections such as `hooks`
- managed `trustedFolders.json` projection must merge inherited system trust
  entries with agent-local runtime trust entries
- it must install Gemini hook/trust state only inside that managed home
- it must write the effective `gemini_home` and `gemini_root` into the agent
  session file
- it must not create, delete, or rewrite project-level `.gemini/settings.json`
  during startup

Absent an explicit validated provider-profile runtime home, the managed
agent-scoped private `HOME` is the default authority.

Startup must fail clearly or mark the agent degraded when the requested managed
home cannot be prepared. It must not silently fall back to the caller's global
Gemini home.

## 5. Binding Contract

Managed Gemini session reading has exactly two modes:

- `bootstrap`
  - used when the agent is not yet bound to a concrete Gemini conversation
  - may scan for a candidate session only within that agent's own managed
    `gemini_root`
  - may use `work_dir` only as a filter inside that managed root
- `bound`
  - used after `gemini_session_id` or `gemini_session_path` exists
  - must prefer the bound session
  - must verify the bound path remains inside that agent's managed Gemini home
  - must not drift to a newer workspace session outside explicit rebinding logic

Binding logic must not use shared `work_dir` as the cross-agent reconciliation
key.

Managed readers must not widen their search to global `~/.gemini/tmp`, even
when they can observe matching workspace paths there. A session outside the
managed home is a contract violation or legacy-leak diagnostic, not a
completion source.

## 6. Isolation Contract

By default:

- two `ccb`-managed Gemini agents must not share a Gemini home
- two `ccb`-managed Gemini agents must not share a Gemini temp root
- two `inplace` Gemini agents may share the same `work_dir`, but must still
  remain isolated
- a non-`ccb` Gemini conversation started in the same working directory must
  not be implicitly adopted by a managed agent

Therefore `ccb` and a manually-run `gemini` command in the project directory
are separate worlds:

- the manual command may use the user's normal `~/.gemini`
- the managed agent must use its agent-scoped private `HOME`
- shared `cwd` or matching request text does not merge their conversations

## 7. Compatibility Contract

To avoid breaking restore for older managed sessions, startup may reuse and
migrate a previously recorded Gemini home when it is already persisted in the
agent session authority.

Compatibility reuse is evidence-driven migration support only. New managed
launches must write the current explicit `gemini_home` and `gemini_root`
contract back to authority.

Legacy session evidence pointing to global `~/.gemini/tmp` or another
non-managed home must not be silently adopted during normal startup.
Persisted session home evidence may be reused only when the resolved
`gemini_home` is inside this agent's current managed home boundary or an
explicit validated provider-profile home. Otherwise it is diagnostic legacy
leak evidence, not restore authority.

`ccb -n` remains a valid way to rebuild a project with fresh managed homes. The
first post-reset startup must force `restore=false` as defined by the startup
contract, so old provider-global history is not silently reattached.

## 8. Diagnostics Contract

When managed Gemini state lives inside the project under
`.ccb/agents/<agent>/provider-state/gemini/`, diagnostics and support bundles
should treat that provider-state tree as project-local evidence.

Diagnostics export should include:

- managed home summary metadata
- managed Gemini temp-root paths and related project-local session files
- non-secret isolated hook/trust overlays when present
- explicit contract-violation evidence when Gemini writes outside the managed
  home

Diagnostics export must exclude copied credential files and projected auth
state.
