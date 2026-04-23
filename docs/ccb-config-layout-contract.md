# CCB Config And Layout Contract

## 1. Purpose

This document defines the non-drifting user-facing contract for project configuration, pane layout, and mux presentation in `ccb_source`.

It is the authoritative design anchor for:

- `.ccb/ccb.config`
- compact layout grammar
- default bootstrap layout generation
- pane naming and pane color identity
- mux split sizing rules for the project UI

## 2. User-Facing Config Contract

- `.ccb/ccb.config` is the only user-facing project config file.
- New projects must bootstrap `.ccb/ccb.config`.
- User help text, validation output, diagnostics, and docs must point to `.ccb/ccb.config`.
- `.ccb/config.yaml` is not part of the contract and must not be read or written by current code.

## 3. Compact Layout Grammar

The primary config format is compact text.

Leaf tokens:

- `cmd`
- `agent_name:provider`

Operators:

- `;`
  - horizontal split, left to right
- `,`
  - vertical split, top to bottom
- `(...)`
  - explicit grouping

Operator precedence:

1. `,`
2. `;`

Examples:

- `cmd; agent1:codex`
- `cmd; agent1:codex, agent2:claude`
- `cmd, agent1:codex; agent2:codex, agent3:claude`
- `cmd, agent1:codex; agent2:codex, (agent3:claude; agent4:gemini)`

## 4. Semantic Rules

- `cmd` is reserved and must not declare a provider.
- Each configured agent must appear exactly once in the layout.
- `cmd` may appear at most once.
- When `cmd` is enabled, `cmd` must be the first leaf in layout traversal so the invoking pane remains the command pane anchor.
- Compact config leaf order defines `default_agents`.
- Rich `ccb.config` formats may define agents separately, but must still provide a `layout` compatible with the same leaf rules.

## 5. Default Layout Contract

Bootstrap must generate a balanced two-column layout over all visible panes.

For `cmd + N agents`:

- 1 agent: `cmd; agent1`
- 2 agents: `cmd; agent1, agent2`
- 3 agents: `cmd, agent1; agent2, agent3`
- 4 agents: `cmd, agent1; agent2, agent3, agent4`

General rule:

- split the full pane list into left and right halves
- stack each half vertically
- keep pane areas uniform by sizing each split according to descendant leaf counts

## 6. Mux Layout Execution Contract

- The current pane is the `cmd` anchor pane.
- Layout execution must prune the configured layout to the requested foreground agent subset plus `cmd`.
- Layout execution must first build a normalized visible-layout plan from `parse -> prune -> render`, and that normalized render is the visible layout signature.
- Layout execution must preserve the relative structure of the configured layout after pruning.
- Recursive split percentages must be computed from leaf-count ratios, not hardcoded repeated `50%` splits.
- Pane pruning must never silently reorder agents.
- Incremental in-place splitting on top of an already materialized project namespace is not a valid way to realize a different visible layout signature.
- When the desired visible layout signature changes, startup must recreate the project namespace before rematerializing panes through the active mux backend.

## 7. Pane Presentation Contract

- `.ccb/ccb.config` logical leaf names are the only authority for pane display names.
- Pane titles must be the exact logical names:
  - `cmd`
  - `agent1`, `agent2`, ...
- Pane border labels must show the logical pane name, not backend-specific pane numbers.
- Provider-specific pane markers such as `CCB-agent1-...` are internal runtime evidence only:
  - they may be persisted in provider session files
  - they must not override pane titles, pane headers, or focus labels in the project namespace UI
- Pane user options and visible titles must be reconciled back to the configured logical name whenever a project-owned pane is reused or rebound.
- The command pane and agent panes must have stable, distinct color identities.
- Pane styling is session-scoped CCB UI state and must not permanently overwrite unrelated user mux themes.

## 8. Project Namespace UI Contract

- Platform mapping is backend-driven, not config-driven:
  - Linux/macOS/WSL use `backend_family=tmux` with `backend_impl=tmux`
  - Native Windows uses `backend_family=tmux` with `backend_impl=psmux`
- The project-owned mux namespace is responsible for its own theme and pane header rendering.
- Project UI correctness must not depend on whether the invoking shell is already inside some outer tmux server or outside on a native Windows terminal host.
- Namespace creation or reuse must reapply session-scoped CCB UI options on the authoritative project namespace.
- When a project-owned pane dies and the daemon chooses namespace-level recovery, it must recreate and re-project the configured layout so each logical pane returns to its canonical position.
- Namespace `layout_version` is the compatibility key for visible pane topology and mux UI presentation:
  - when the stored namespace layout version differs from the current code contract, the project namespace must be recreated
  - recreating the namespace is the preferred healing path for stale pane geometry or stale session-scoped UI options
- Namespace state must also track the current visible layout signature derived from `.ccb/ccb.config` after foreground pruning.
- If the stored visible layout signature differs from the desired visible layout signature for the current foreground start, the namespace must be recreated instead of trying to patch geometry in place.

## 9. Update Discipline

- If `.ccb/ccb.config` grammar changes, update this document in the same patch.
- If bootstrap layout defaults change, update this document in the same patch.
- If pane naming, split sizing, or pane theming rules change materially, update this document in the same patch.
