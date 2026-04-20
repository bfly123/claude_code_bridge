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

<!-- REVIEW_RUBRICS_START -->
## Review Rubrics & Templates

When you receive a review request from the `designer`, use these rubrics to score each dimension individually.

### Rubric A: Plan Review (5 dimensions, each 1-10)

| # | Dimension | What to evaluate |
|---|---|---|
| 1 | Clarity | Unambiguous steps; another developer can follow without questions |
| 2 | Completeness | All requirements, edge cases, and deliverables covered |
| 3 | Feasibility | Steps achievable with current codebase and dependencies |
| 4 | Risk Assessment | Risks identified with concrete mitigations |
| 5 | Requirement Alignment | Every step traces to a stated requirement; no scope creep |

**Pass**: all 5 dimensions = 10. No weighted average — every dimension must independently reach 10.

### Rubric B: Code Review (6 dimensions, each 1-10)

| # | Dimension | What to evaluate |
|---|---|---|
| 1 | Correctness | Code does what the plan specified; no logic bugs |
| 2 | Security | No injection, no hardcoded secrets, proper input validation |
| 3 | Maintainability | Clean code, good naming, follows project conventions |
| 4 | Performance | No unnecessary O(n²), no blocking calls, efficient resource use |
| 5 | Test Coverage | New/changed paths covered by tests; tests pass |
| 6 | Plan Adherence | Implementation matches the approved plan |

**Pass**: all 6 dimensions = 10. No weighted average — every dimension must independently reach 10.

### Response Format

When scoring, return JSON with this structure.

#### Plan Review Response

```json
{
  "review_type": "plan",
  "dimensions": {
    "clarity": { "score": N, "strengths": ["..."], "weaknesses": ["..."], "fix": "..." },
    "completeness": { "score": N, "strengths": ["..."], "weaknesses": ["..."], "fix": "..." },
    "feasibility": { "score": N, "strengths": ["..."], "weaknesses": ["..."], "fix": "..." },
    "risk_assessment": { "score": N, "strengths": ["..."], "weaknesses": ["..."], "fix": "..." },
    "requirement_alignment": { "score": N, "strengths": ["..."], "weaknesses": ["..."], "fix": "..." }
  },
  "overall": N.N,
  "critical_issues": ["blocking issues that MUST be fixed"],
  "summary": "one-paragraph overall assessment"
}
```

#### Code Review Response

```json
{
  "review_type": "code",
  "dimensions": {
    "correctness": { "score": N, "strengths": ["..."], "weaknesses": ["..."], "fix": "..." },
    "security": { "score": N, "strengths": ["..."], "weaknesses": ["..."], "fix": "..." },
    "maintainability": { "score": N, "strengths": ["..."], "weaknesses": ["..."], "fix": "..." },
    "performance": { "score": N, "strengths": ["..."], "weaknesses": ["..."], "fix": "..." },
    "test_coverage": { "score": N, "strengths": ["..."], "weaknesses": ["..."], "fix": "..." },
    "plan_adherence": { "score": N, "strengths": ["..."], "weaknesses": ["..."], "fix": "..." }
  },
  "overall": N.N,
  "critical_issues": ["blocking issues that MUST be fixed"],
  "summary": "one-paragraph overall assessment"
}
```
<!-- REVIEW_RUBRICS_END -->
