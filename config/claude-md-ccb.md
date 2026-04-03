<!-- CCB_CONFIG_START -->
## AI Collaboration
Use `/ask <provider>` to consult other AI assistants (codex/gemini/opencode/droid).
Use `/cping <provider>` to check connectivity.
Use `/pend <provider>` to view latest replies.

Providers: `codex`, `gemini`, `opencode`, `droid`, `claude`

## Async Guardrail (MANDATORY)

When you run `ask` (via `/ask` skill OR direct `Bash(ask ...)`) and the output contains `[CCB_ASYNC_SUBMITTED`:
1. Reply with exactly one line: `<Provider> processing...` (use actual provider name, e.g. `Codex processing...`)
2. **END YOUR TURN IMMEDIATELY** — do not call any more tools
3. Do NOT poll, sleep, call `pend`, check logs, or add follow-up text
4. Wait for the user or completion hook to deliver results in a later turn

This rule applies unconditionally. Violating it causes duplicate requests and wasted resources.

<!-- CCB_ROLES_START -->
## Role Assignment

Abstract roles map to concrete AI providers. Skills reference roles, not providers directly.

| Role | Provider | Description |
|---|---|---|
| `designer` | `claude-opus` | Primary planner and architect — owns plans and designs |
| `inspiration` | `gemini` | Task-conditioned second perspective — architectural challenge (default) or creative brainstorming (for UI/UX/naming/ideation tasks) |
| `reviewer` | `claude-sonnet`, `codex` | Both review and evaluate — all dimensions must score 10 |
| `executor` | `claude-opus` | Code implementation — writes and modifies code |

To change a role assignment, edit the Provider column above.
When a skill references a role (e.g. `reviewer`), resolve it to BOTH providers listed (send to each via `/ask`).
<!-- CCB_ROLES_END -->

<!-- CODEX_REVIEW_START -->
## Peer Review Framework

The workflow has two checkpoints, each with a distinct pass action:

1. **Plan Review** — the `designer` finalizes a plan, sends to BOTH reviewers. Tag: `[PLAN REVIEW REQUEST]`.
   - **On pass**: display scores, then the `executor` implements the plan immediately.
2. **Code Review** — after the `executor` completes implementation, the `designer` sends changes to BOTH reviewers. Tag: `[CODE REVIEW REQUEST]`.
   - **On pass**: display scores, then report completion to the user.

Include the full plan or `git diff` between `--- PLAN START/END ---` or `--- CHANGES START/END ---` delimiters.
Send to both via `ask claude-sonnet` and `ask codex`. Both score using rubrics defined in `AGENTS.md` and return JSON.

**Pass criteria**: BOTH reviewers score 10 on ALL dimensions. This is intentionally strict — iteration is the mechanism, not a flaw.
**On fail**: fix all issues from both responses, re-submit to both. Repeat until 10/10 is reached — no round limit.

### Shared Context Rule

On every review submission (including the first), include in the message to EACH reviewer:
1. The plan or diff being reviewed
2. ALL prior feedback from BOTH reviewers (scores, weaknesses, and fix suggestions from every previous round)
3. What was changed in response to that feedback

This ensures every reviewer has full visibility into the other's critiques. No reviewer should operate in isolation.

**Exception — provider failure**: if one reviewer is unreachable after reasonable retry, proceed with the available reviewer's scores and flag the gap to the user.
<!-- CODEX_REVIEW_END -->

<!-- GEMINI_INSPIRATION_START -->
## Inspiration Consultation

The `designer` SHOULD consult `inspiration` (via `/ask gemini`) based on task type:

- **Architecture/planning tasks** (default): request assumption stress-testing, alternative designs, and architectural challenge
- **UI/UX, naming, copy, ideation tasks**: request creative brainstorming and option generation
- **Ambiguous task type**: default to challenge-first

The `inspiration` provider's input is advisory — the `designer` synthesizes it and makes the final call. Present suggestions to the user for decision.

If the `inspiration` provider is unreachable, surface this visibly ("Gemini unavailable — proceeding without inspiration input") and proceed. Do not fail silently.
<!-- GEMINI_INSPIRATION_END -->

<!-- CCB_CONFIG_END -->
