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
2. **Inspiration Brainstorming** - Creative ideas from `inspiration` (reference only)
3. **Design** - `designer` creates the full plan, integrating adopted ideas
4. **Scored Review** - `reviewer` scores using Rubric A (must pass >= 7.0)
5. **Final Output** - Actionable plan saved to `plans/` directory

## Roles Used

| Role | Responsibility |
|------|---------------|
| `designer` | Primary planner, owns the plan |
| `inspiration` | Creative consultant (unreliable, user decides) |
| `reviewer` | Quality gate (Rubric A, per-dimension scoring) |

Roles resolve to providers via CLAUDE.md `CCB_ROLES` table.

## Key Features

- **Structured Clarification**: 5-Dimension readiness scoring (100 pts)
- **Inspiration Filter**: Adopt / Adapt / Discard with user approval
- **Scored Quality Gate**: Dimension-level scoring, auto-correction (max 3 rounds)
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
