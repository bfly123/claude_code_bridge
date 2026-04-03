# All Plan (Droid Version)

Planning skill using abstract roles defined in CLAUDE.md Role Assignment table.

**Usage**: For complex features or architectural decisions requiring thorough planning.

**Roles used by this skill** (resolve to providers via CLAUDE.md `CCB_ROLES`):
- `designer` — Primary planner, owns the plan from start to finish
- `inspiration` — Task-conditioned second perspective: architectural challenge (default) or creative brainstorming (for UI/UX/naming/ideation tasks). Advisory — the `designer` synthesizes input and makes the final call. If unreachable, surface visibly ("Gemini unavailable — proceeding without inspiration input") and proceed.
- `reviewer` — Dual scored quality gate (`claude-sonnet` + `codex`). Both score using Rubric A — all dimensions must reach 10. Iterate until pass, no round limit.

---

## Input Parameters

From `$ARGUMENTS`:
- `requirement`: User's initial requirement or feature request
- `context`: Optional project context or constraints

---

## Execution Flow

### Phase 1: Requirement Clarification

**1.1 Structured Clarification (Option-Based)**

Use the **5-Dimension Planning Readiness Model** to ensure comprehensive requirement capture.

#### Readiness Dimensions (100 pts total)

| Dimension | Weight | Focus | Priority |
|-----------|--------|-------|----------|
| Problem Clarity | 30pts | What problem? Why solve it? | 1 |
| Functional Scope | 25pts | What does it DO? Key features | 2 |
| Success Criteria | 20pts | How to verify done? | 3 |
| Constraints | 15pts | Time, resources, compatibility | 4 |
| Priority/MVP | 10pts | What first? Phased delivery? | 5 |

#### Clarification Flow

```
ROUND 1:
  1. Parse initial requirement
  2. Identify 2 lowest-confidence dimensions (use Priority order for ties)
  3. Present 2 questions with options (1 per dimension)
  4. User selects options
  5. Update dimension scores based on answers
  6. Display Scorecard to user

IF readiness_score >= 80: Skip Round 2, proceed to 1.2
ELSE:
  ROUND 2:
    1. Re-identify 2 lowest-scoring dimensions
    2. Ask 2 more questions
    3. Update scores
    4. Proceed regardless (with gap summary)

QUICK-START OVERRIDE:
  - User can select "Proceed anyway" at any point
  - All dimensions marked as "assumption" in summary
```

#### Option Bank Reference

**Problem Clarity (30pts)**
```
Question: "What type of problem are you solving?"
Options:
  A. "Specific bug or defect with clear reproduction" → 27pts
  B. "New feature with defined business value" → 27pts
  C. "Performance/optimization improvement" → 24pts
  D. "General improvement or refactoring" → 18pts
  E. "Not sure yet - need exploration" → 9pts (flag)
  F. "Other: ___" → 12pts (flag)
```

**Functional Scope (25pts)**
```
Question: "What is the scope of functionality?"
Options:
  A. "Single focused component/module" → 23pts
  B. "Multiple related components" → 20pts
  C. "Cross-cutting system change" → 18pts
  D. "Unclear - need codebase analysis" → 10pts (flag)
  E. "Other: ___" → 10pts (flag)
```

**Success Criteria (20pts)**
```
Question: "How will you verify success?"
Options:
  A. "Automated tests (unit/integration/e2e)" → 18pts
  B. "Performance benchmarks with targets" → 18pts
  C. "Manual testing with checklist" → 14pts
  D. "User feedback/acceptance" → 12pts
  E. "Not defined yet" → 6pts (flag)
  F. "Other: ___" → 8pts (flag)
```

**Constraints (15pts)**
```
Question: "What are the primary constraints?"
Options:
  A. "Time-sensitive (deadline driven)" → 14pts
  B. "Must maintain backward compatibility" → 14pts
  C. "Resource/budget limited" → 12pts
  D. "Security/compliance critical" → 14pts
  E. "No specific constraints" → 10pts
  F. "Other: ___" → 8pts (flag)
```

**Priority/MVP (10pts)**
```
Question: "What is the delivery approach?"
Options:
  A. "MVP first, iterate later" → 9pts
  B. "Full feature, single release" → 9pts
  C. "Phased rollout planned" → 9pts
  D. "Exploratory - scope TBD" → 5pts (flag)
  E. "Other: ___" → 5pts (flag)
```

#### Gap Classification Rules

| Dimension Score | Classification | Handling |
|-----------------|----------------|----------|
| ≥70% of weight | ✓ Defined | Include in Design Brief |
| 50-69% of weight | ⚠️ Assumption | Carry forward as risk |
| <50% of weight | 🚫 Gap | Flag in brief, may need validation |

Example thresholds:
- Problem Clarity: ≥21 Defined, 15-20 Assumption, <15 Gap
- Functional Scope: ≥18 Defined, 13-17 Assumption, <13 Gap
- Success Criteria: ≥14 Defined, 10-13 Assumption, <10 Gap
- Constraints: ≥11 Defined, 8-10 Assumption, <8 Gap
- Priority/MVP: ≥7 Defined, 5-6 Assumption, <5 Gap

#### Clarification Summary Output

After clarification, generate:

```
CLARIFICATION SUMMARY
=====================
Readiness Score: [X]/100

Dimensions:
- Problem Clarity: [X]/30 [✓/⚠️/🚫]
- Functional Scope: [X]/25 [✓/⚠️/🚫]
- Success Criteria: [X]/20 [✓/⚠️/🚫]
- Constraints: [X]/15 [✓/⚠️/🚫]
- Priority/MVP: [X]/10 [✓/⚠️/🚫]

Assumptions & Gaps:
- [Dimension]: [assumption or gap description]

Proceeding to project analysis...
```

Save as `clarification_summary`.

**1.2 Analyze Project Context**

Use available tools to understand:
- Existing codebase structure (Glob, Grep, Read)
- Current architecture patterns
- Dependencies and tech stack
- Related existing implementations

**1.3 Research (if needed)**

If the requirement involves:
- New technologies or frameworks
- Industry best practices
- Performance benchmarks
- Security considerations

Use WebSearch to gather relevant information.

**1.4 Formulate Design Brief**

Create a comprehensive design brief incorporating clarification results:

```
DESIGN BRIEF
============
Readiness Score: [X]/100

Problem: [clear problem statement]
Context: [project context, tech stack, constraints]

Requirements:
- [requirement 1]
- [requirement 2]

Success Criteria:
- [criterion 1]
- [criterion 2]

Assumptions (from clarification):
- [assumption 1]

Gaps to Validate:
- [gap 1]

Research Findings: [if applicable]
```

Save as `design_brief`.

---

### Phase 2: Inspiration Consultation

Send the design brief to `inspiration` for task-conditioned input. The prompt varies by task type.

**2.1 Request Inspiration**

Send to `inspiration` (via `/ask gemini`). Choose the prompt based on task type:

**For architecture/planning tasks (default):**

```
You are an architectural reviewer and second perspective. Based on this design brief, challenge the assumptions and propose alternatives — not a full implementation plan.

DESIGN BRIEF:
[design_brief]

Provide:
1) 2-3 assumptions in this brief that should be stress-tested
2) 1-2 alternative architectural approaches worth considering
3) Risks or failure modes the brief may have missed
4) Trade-offs the designer should explicitly decide on

Be direct and critical. Your role is to strengthen the plan by challenging it.
```

**For UI/UX, naming, copy, or ideation tasks:**

```
You are a creative brainstorming partner. Based on this design brief, provide INSPIRATION and CREATIVE IDEAS — not a full implementation plan.

DESIGN BRIEF:
[design_brief]

Provide:
1) 3-5 creative approaches or angles others might miss
2) Naming suggestions (for features, APIs, components) if applicable
3) UX/UI ideas or visual design inspiration if applicable
4) Unconventional solutions worth considering
5) Analogies from other domains that could inform the design

Be bold and creative. Practical feasibility is secondary — inspiration is the goal.
```

**If `inspiration` is unreachable:** Surface this visibly ("Gemini unavailable — proceeding without inspiration input") and skip to Phase 3.

Save response as `inspiration_response`.

**2.2 The `designer` Filters Inspiration Ideas**

After receiving the response, the `designer` MUST:

1. Read all suggestions critically
2. Classify each idea:
   - **Adopt** — genuinely improves the design, feasible within constraints
   - **Adapt** — interesting kernel but needs reworking to be practical
   - **Discard** — creative but impractical, off-target, or contradicts requirements
3. Present the filtered list to the user:

```
INSPIRATION FILTER
==========================
Adopted:
- [idea]: [why it's valuable]

Adapted:
- [idea] → [how the `designer` will modify it]: [rationale]

Discarded:
- [idea]: [why it doesn't fit]
```

4. Ask user: "Do you agree with this selection, or want to override any decisions?"

Save filtered result as `adopted_inspiration`.

---

### Phase 3: The `designer` Creates the Plan

The `designer` is the sole planner. Use the design brief, project context, research findings, and adopted inspiration to create a complete implementation plan.

**3.1 Draft the Plan**

```
IMPLEMENTATION PLAN (Draft v1)
==============================
Goal: [1-sentence goal]

Architecture:
- Approach: [chosen approach with rationale]
- Key Components: [list]
- Data Flow: [if applicable]

Implementation Steps:
1. [Step title]
   - Actions: [specific actions]
   - Deliverables: [what will be produced]
   - Dependencies: [what's needed first]
2. [Step title]
   ...

Technical Considerations:
- [consideration 1]
- [consideration 2]

Risks & Mitigations:
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| [risk] | H/M/L | H/M/L | [strategy] |

Acceptance Criteria:
- [ ] [criterion 1]
- [ ] [criterion 2]

Inspiration Credits (from `inspiration`):
- [adopted idea and how it was integrated]
```

Save as `plan_draft_v1`.

---

### Phase 4: Scored Review

Submit the plan to BOTH reviewers for scored review using Rubric A (defined in AGENTS.md).

**4.1 Submit Plan for Review**

Send to BOTH reviewers (via `/ask claude-sonnet` AND `/ask codex`):

```
[PLAN REVIEW REQUEST]
Review the following implementation plan using Rubric A. Score EACH dimension individually with detailed feedback.
Return your response as JSON with this exact structure:
{
  "review_type": "plan",
  "dimensions": {
    "clarity": {
      "score": N,
      "strengths": ["..."],
      "weaknesses": ["..."],
      "fix": "specific action to improve"
    },
    "completeness": {
      "score": N,
      "strengths": ["..."],
      "weaknesses": ["..."],
      "fix": "specific action to improve"
    },
    "feasibility": {
      "score": N,
      "strengths": ["..."],
      "weaknesses": ["..."],
      "fix": "specific action to improve"
    },
    "risk_assessment": {
      "score": N,
      "strengths": ["..."],
      "weaknesses": ["..."],
      "fix": "specific action to improve"
    },
    "requirement_alignment": {
      "score": N,
      "strengths": ["..."],
      "weaknesses": ["..."],
      "fix": "specific action to improve"
    }
  },
  "overall": N.N,
  "critical_issues": ["..."],
  "summary": "one-paragraph overall assessment"
}

--- PLAN START ---
[plan_draft_v1]
--- PLAN END ---
```

**4.2 Parse and Judge**

After receiving BOTH reviewers' JSON responses:

```
iteration = 1

CHECK:
  - If BOTH reviewers score 10 on ALL dimensions → PASS
  - Otherwise → FAIL
```

**4.3 Iteration Loop (on FAIL)**

```
WHILE result == FAIL:
  1. Read ALL feedback from BOTH reviewers (scores, weaknesses, fix suggestions)
  2. Read critical_issues lists from both
  3. Revise plan_draft to address ALL issues from BOTH reviewers
  4. Save as plan_draft_v{iteration+1}
  5. Re-submit to BOTH reviewers via /ask (include: the revised plan, ALL prior feedback from BOTH reviewers, and what was changed in response)
  6. iteration += 1
  7. Re-check PASS/FAIL

No round limit — iterate until 10/10 is reached.
Exception: if one reviewer is unreachable after reasonable retry, proceed with the available reviewer's scores and flag the gap to the user.
```

**4.4 Display Score Summary (on PASS)**

```
REVIEW: PASSED (Round [N])
=================================
Reviewer: claude-sonnet
| Dimension             | Score |
|-----------------------|-------|
| Clarity               | 10/10 |
| Completeness          | 10/10 |
| Feasibility           | 10/10 |
| Risk Assessment       | 10/10 |
| Requirement Alignment | 10/10 |

Reviewer: codex
| Dimension             | Score |
|-----------------------|-------|
| Clarity               | 10/10 |
| Completeness          | 10/10 |
| Feasibility           | 10/10 |
| Risk Assessment       | 10/10 |
| Requirement Alignment | 10/10 |

Key Strengths:
- [from `reviewer` response]

Addressed Issues:
- [issues fixed during iteration, if any]
```

---

### Phase 5: Final Output

**5.1 Save Plan Document**

Write the final plan to a markdown file:

**File path**: `plans/{feature-name}-plan.md`

Use this template:

```markdown
# {Feature Name} - Solution Design

> Generated by all-plan (`designer` + `inspiration` + `reviewer`)

## Overview

**Goal**: [Clear, concise goal statement]

**Readiness Score**: [X]/100

**Review**: Passed round [N] (all dimensions 10/10 from both reviewers)

**Generated**: [Date]
```

The plan document should also include these sections (continue the markdown template):

```markdown
## Requirements Summary

### Problem Statement
[Clear problem description]

### Scope
[What's in scope and out of scope]

### Success Criteria
- [ ] [criterion 1]
- [ ] [criterion 2]

### Constraints
- [constraint 1]

### Assumptions
- [assumption from clarification]
```

Continue the plan document with:

```markdown
## Architecture

### Approach
[Chosen architecture approach with rationale]

### Key Components
- **[Component 1]**: [description]
- **[Component 2]**: [description]

### Data Flow
[If applicable, describe data flow]
```

Continue with implementation and risk sections:

```markdown
## Implementation Plan

### Step 1: [Title]
- **Actions**: [specific actions]
- **Deliverables**: [what will be produced]
- **Dependencies**: [what's needed first]

### Step 2: [Title]
- **Actions**: [specific actions]
- **Deliverables**: [what will be produced]
- **Dependencies**: [what's needed first]

[Continue for all steps...]

---

## Technical Considerations

- [consideration 1]
- [consideration 2]

---

## Risk Management

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| [risk 1] | High/Med/Low | High/Med/Low | [strategy] |
| [risk 2] | High/Med/Low | High/Med/Low | [strategy] |

---

## Acceptance Criteria

- [ ] [criterion 1]
- [ ] [criterion 2]
- [ ] [criterion 3]
```

Finish the plan document with credits and appendix:

```markdown
---

## Inspiration Credits

| Idea | Status | How Integrated |
|------|--------|----------------|
| [idea 1] | Adopted | [how it was used] |
| [idea 2] | Adapted | [how it was modified] |

---

## Review Summary

| Dimension | claude-sonnet | codex |
|-----------|-------|-------|
| Clarity | X/10 | X/10 |
| Completeness | X/10 | X/10 |
| Feasibility | X/10 | X/10 |
| Risk Assessment | X/10 | X/10 |
| Requirement Alignment | X/10 | X/10 |

Review rounds: [N] | Pass: all dimensions 10/10 from both reviewers

---

## Appendix

### Clarification Summary
[Include the clarification summary from Phase 1.1]

### Discarded Inspiration Ideas
[Ideas considered but not adopted, with rationale]

### Alternative Approaches Considered
[Brief notes on approaches evaluated but not chosen]
```

**5.2 Output to User**

After saving the file, display to user:

```
PLAN COMPLETE
=============

✓ Plan saved to: plans/{feature-name}-plan.md

Summary:
- Goal: [1-sentence goal]
- Steps: [N] implementation steps
- Risks: [N] identified with mitigations
- Readiness: [X]/100
- Review: Passed round [N] (all dimensions 10/10 from both reviewers)
- Inspiration Ideas: [N] adopted, [N] adapted, [N] discarded

Next: Review the plan and proceed with implementation when ready.
```

---

## Principles

1. **`designer` Owns the Design**: The `designer` is the sole planner; `inspiration` and `reviewer` are consultants
2. **Structured Clarification**: Use option-based questions to systematically capture requirements
3. **Readiness Scoring**: Quantify requirement completeness before proceeding
4. **`inspiration` is Advisory**: Task-conditioned input (architectural challenge or creative brainstorming) — the `designer` synthesizes and decides
5. **User Controls Inspiration**: User decides which ideas to adopt/discard
6. **Dual `reviewer` Quality Gate**: Plan must pass Rubric A (all dimensions = 10 from BOTH reviewers) before proceeding
7. **Dimension-Level Feedback**: Both reviewers score each dimension individually with actionable fixes
8. **Iterate Until Pass**: No round limit — shared context ensures reviewers see each other's feedback
9. **Concrete Deliverables**: Output actionable plan document, not just discussion notes
10. **Research When Needed**: Use WebSearch for external knowledge when applicable

---

## Notes

- This skill is designed for complex features or architectural decisions
- For simple tasks, use direct implementation instead
- Resolve `inspiration` to provider via CLAUDE.md Role Assignment (`/ask gemini`); resolve `reviewer` to BOTH providers (`/ask claude-sonnet` AND `/ask codex`)
- If `inspiration` provider is unreachable, surface visibly ("Gemini unavailable — proceeding without inspiration input") and skip to Phase 3
- If one reviewer is unreachable, proceed with the available reviewer and flag the gap to user
- If both reviewers are unavailable, present the plan directly to user
- Plans are saved to `plans/` directory with descriptive filenames
