# Claude Session Isolation Contract

## 1. Purpose

This document defines the non-drifting contract for `ccb`-managed Claude home
and session isolation.

It is the authoritative design anchor for:

- `claude` startup environment under `ccb`
- agent-scoped Claude provider state layout
- Claude home and projects/session-env root persistence
- Claude bootstrap binding vs bound-session reading
- isolation from non-`ccb` Claude conversations

This document complements, but does not replace, the project startup contract in
[docs/ccbd-startup-supervision-contract.md](/home/bfly/yunwei/ccb_source/docs/ccbd-startup-supervision-contract.md).

## 2. Identity Model

`ccb` must treat these identities as distinct:

- `agent identity`
  - project anchor + logical agent name + provider
- `runtime generation`
  - one launch generation, currently represented by `ccb_session_id`
- `provider conversation identity`
  - the concrete Claude conversation, represented by `claude_session_id`

`work_dir` is context only. It must not be treated as the primary identity for a
managed Claude agent.

The effective managed `HOME` is the provider-state boundary for Claude under
`ccb`. `~/.claude/projects` and `~/.claude/session-env` are derived state inside
that managed boundary, not independent isolation authorities.

Operational constraint:

- Claude Code does not expose a stable dedicated `CLAUDE_HOME` flag
- managed isolation therefore requires a private `HOME` projection
- setting only `CLAUDE_PROJECTS_ROOT` is not sufficient, because Claude also
  reads other state under `HOME`

## 3. Storage Contract

For a managed Claude agent named `<agent>`:

- runtime artifacts live under:
  - `.ccb/agents/<agent>/provider-runtime/claude/`
- stable provider state lives under:
  - `.ccb/agents/<agent>/provider-state/claude/`

By default, the managed Claude home is:

- `.ccb/agents/<agent>/provider-state/claude/home/`

Inside that home, the managed Claude state is:

- `.ccb/agents/<agent>/provider-state/claude/home/.claude/projects/`
- `.ccb/agents/<agent>/provider-state/claude/home/.claude/session-env/`
- `.ccb/agents/<agent>/provider-state/claude/home/.claude/settings.json`
- `.ccb/agents/<agent>/provider-state/claude/home/.claude.json`

If the effective Claude home is explicitly overridden by a provider profile, the
effective projects root and session-env root must still be derived from that
home:

- `<claude_home>/.claude/projects/`
- `<claude_home>/.claude/session-env/`

Two configured Claude agents must not resolve to the same effective
`claude_home` unless a future explicit shared-home mode declares and validates
that weaker isolation contract.

The managed session file must persist:

- `claude_home`
- `claude_projects_root`
- `claude_session_env_root`
- `claude_session_id` once bound
- `claude_session_path` once bound

These fields are authority for managed Claude runtime recovery.

Credential and config projection is not conversation identity. `ccb` may project
the user's source Claude auth/config into the private managed home so the
provider can authenticate, but projected secret material must not be exported by
diagnostics.

## 4. Startup Contract

When `ccb` starts a managed Claude agent:

- it must explicitly set the effective `HOME`
- it must explicitly set the effective `CLAUDE_PROJECTS_ROOT`
- it must ensure `CLAUDE_PROJECTS_ROOT == <claude_home>/.claude/projects`
- it must create the managed home, projects root, and session-env root before
  launching Claude
- it must materialize required Claude auth/config projections into the managed
  home without treating them as conversation identity
- it must install Claude hook/trust state only inside that managed home
- it must write the effective `claude_home`, `claude_projects_root`, and
  `claude_session_env_root` into the agent session file
- it must not rely on global `~/.claude/projects` as the default managed Claude
  namespace
- it must not create, delete, or rewrite project-level `.claude/settings.json`
  or `.claude/settings.local.json` during startup

Absent an explicit validated provider-profile runtime home, the managed
agent-scoped private `HOME` is the default authority.

Startup must fail clearly or mark the agent degraded when the requested managed
home cannot be prepared. It must not silently fall back to the caller's global
Claude home.

## 5. Binding Contract

Managed Claude session reading has exactly two modes:

- `bootstrap`
  - used when the agent is not yet bound to a concrete Claude conversation
  - may scan for a candidate session only within that agent's own managed
    `claude_projects_root`
  - may use `work_dir` only as a filter inside that managed home
- `bound`
  - used after `claude_session_id` or `claude_session_path` exists
  - must prefer the bound session
  - must verify the bound path remains inside that agent's managed Claude home
  - must not drift to a newer workspace session outside explicit rebinding logic

Binding logic must not use shared `work_dir` as the cross-agent reconciliation
key.

Managed readers must not widen their search to global `~/.claude/projects`, even
when they can observe matching workspace paths there. A session outside the
managed home is a contract violation or legacy-leak diagnostic, not a completion
source.

## 6. Isolation Contract

By default:

- two `ccb`-managed Claude agents must not share a Claude home
- two `ccb`-managed Claude agents must not share a Claude projects root
- two `inplace` Claude agents may share the same `work_dir`, but must still
  remain isolated
- a non-`ccb` Claude conversation started in the same working directory must not
  be implicitly adopted by a managed agent

Therefore `ccb` and a manually-run `claude` command in the project directory are
separate worlds:

- the manual command may use the user's normal home and `~/.claude`
- the managed agent must use its agent-scoped private `HOME`
- shared `cwd` or matching request text does not merge their conversations

## 7. Compatibility Contract

To avoid breaking restore for older managed sessions, startup may reuse and
migrate a previously recorded Claude home when it is already persisted in the
agent session authority.

Compatibility reuse is evidence-driven migration support only. New managed
launches must write the current explicit `claude_home`, `claude_projects_root`,
and `claude_session_env_root` contract back to authority.

Legacy session evidence pointing to global `~/.claude/projects` or another
non-managed home must not be silently adopted during normal startup.
Persisted session home evidence may be reused only when the resolved
`claude_home` is inside this agent's current managed home boundary or an
explicit validated provider-profile home. Otherwise it is diagnostic legacy
leak evidence, not restore authority.

`ccb -n` remains a valid way to rebuild a project with fresh managed homes. The
first post-reset startup must force `restore=false` as defined by the startup
contract, so old provider-global history is not silently reattached.

## 8. Diagnostics Contract

When managed Claude state lives inside the project under
`.ccb/agents/<agent>/provider-state/claude/`, diagnostics and support bundles
should treat that provider-state tree as project-local evidence.

Diagnostics export should include:

- managed home summary metadata
- managed Claude projects/session-env paths and related project-local session
  files
- non-secret isolated settings overlays when present
- explicit contract-violation evidence when Claude writes outside the managed
  home

Diagnostics export must exclude copied credential files and projected trust/auth
state.
