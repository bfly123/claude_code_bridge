---
name: all-plan
description: Collaborative planning using abstract roles (designer + inspiration + reviewer).
metadata:
  short-description: designer plans + inspiration challenges/brainstorms + dual reviewer scores (10/10)
---

# All Plan (Claude Version)

Collaborative planning using abstract roles defined in CLAUDE.md Role Assignment table.

Highlights:
- 5-Dimension requirement clarification (retained)
- `inspiration` provides task-conditioned input: architectural challenge (default) or creative brainstorming (UI/UX/naming/ideation)
- `designer` creates the full plan independently
- `reviewer` (both `claude-sonnet` and `codex`) scores the plan — all dimensions must reach 10
- Iterate until 10/10 — no round limit

For full instructions, see `references/flow.md`
