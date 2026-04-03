# All-Plan Skill

Collaborative planning using abstract roles defined in CLAUDE.md Role Assignment table.

## Usage

```
/all-plan <your requirement or feature request>
```

Example:
```
/all-plan Design a caching layer for the API with Redis
```

## How It Works

**5-Phase Design Process:**

1. **Requirement Clarification** - 5-Dimension readiness model, structured Q&A
2. **Inspiration Consultation** - Task-conditioned input from `inspiration`: architectural challenge (default) or creative brainstorming (UI/UX/naming/ideation)
3. **Design** - `designer` creates the full plan, integrating adopted ideas
4. **Dual Scored Review** - Both reviewers (`claude-sonnet` + `codex`) score using Rubric A — all dimensions must reach 10
5. **Final Output** - Actionable plan saved to `plans/` directory

## Roles Used

| Role | Responsibility |
|------|---------------|
| `designer` | Primary planner, owns the plan |
| `inspiration` | Task-conditioned second perspective (architectural challenge or creative brainstorming) |
| `reviewer` | Dual quality gate — both `claude-sonnet` and `codex` score (all dimensions must reach 10) |

Roles resolve to providers via CLAUDE.md `CCB_ROLES` table.

## Key Features

- **Structured Clarification**: 5-Dimension readiness scoring (100 pts)
- **Inspiration Filter**: Adopt / Adapt / Discard with user approval
- **Dual Scored Quality Gate**: Both reviewers must score 10 on all dimensions — iterate until pass, no round limit
- **Optional Web Research**: Triggered when requirements depend on external info

## When to Use

- Complex features requiring thorough planning
- Architectural decisions with multiple valid approaches
- Tasks involving creative/aesthetic elements (leverages `inspiration`)

## Output

A comprehensive plan including:
- Goal and architecture with rationale
- Implementation steps with dependencies
- Risk management matrix
- Review scores (per-dimension)
- Inspiration credits (adopted/adapted/discarded)
