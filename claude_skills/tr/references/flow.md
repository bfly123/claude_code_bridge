# AutoFlow Run

Execute current step while Claude stays in plan mode and Codex performs all file I/O.

**File formats**: See `~/.claude/skills/docs/formats.md`
**Protocol**: See `~/.claude/skills/docs/protocol.md`

---

## Execution Flow

**Auto-loop daemon**: started by `/tp` (`bash ~/.claude/skills/tr/scripts/autoloop.sh start`). `/tr` should assume it is running and only ensure the finalize request doesn't stop it.

### 1. Sync Current State (Codex)

Claude does not read/modify repo files directly. Request Codex to:
1) read `.ccb/state.json`
2) validate `current`
3) enforce attempt limits
4) (if proceeding) increment attempts and persist back to `.ccb/state.json`
5) return a compact step context for design

Call `/file-op` with `FileOpsREQ`:
- Template: `../templates/preflight.json`

Interpret `FileOpsRES`:
- If no plan → show `No plan. Use /tp first.` → Stop
- If `current.type == "none"` → All done → Show summary → Stop
- If attempts exceeded → request `autoflow_state_mark_blocked` with a reason → Stop
- Otherwise use `data.stepContext` + `data.state.current` for Step Design

### 1.5 Resolve Roles Config

Goal: support `reviewer` / `designer` routing.

Two-layer resolution:

1. **CLAUDE.md Role Assignment table** (primary): Read the Role Assignment table from CLAUDE.md context. The `reviewer` and `designer` roles map to providers.
2. **`.autoflow/roles.json`** (override): If this file exists in the repo, and `enabled == true` and `schemaVersion == 1`, use its fields to override.

Default roles:
- `executor = "codex"`
- `reviewer = "codex"`
- `designer = ["claude", "codex"]`

Implementation detail: Claude must not read repo files directly; request reads via `/file-op` (`read_file`) and parse JSON locally.

### 2. Step Design (Dual Independent Design)

Perform a lightweight dual design for the current step (not the full `/all-plan` flow — step-level design is smaller scope with context already provided by preflight).

#### 2.1 Claude Independent Design (local, no provider call)

Input: current step title + task objective + relevant files + dependencies from preflight

Output JSON:
```json
{
  "approach": "description of implementation approach",
  "doneConditions": ["condition 1", "condition 2"],
  "risks": ["risk 1"],
  "needsSplit": false,
  "splitReason": null,
  "proposedSubsteps": null
}
```

#### 2.2 Codex Independent Design (via `/ask codex`)

```
/ask codex "Independent step design:
Step: [title]
Context: [objective, relevant files, dependencies]
Return JSON only: { approach, doneConditions, risks, needsSplit, splitReason, proposedSubsteps }"
```

#### 2.3 Claude Merge (1-2 rounds, Claude leads)

Compare both designs:
- Take union of `doneConditions` (deduplicate, max 2)
- Take union of `risks` (deduplicate)
- Resolve `approach` conflicts — Claude has final decision
- Resolve `needsSplit` — if either says true, evaluate carefully; Claude decides

**Output contract** (merged JSON):
```json
{
  "approach": "string",
  "doneConditions": ["string", "max 2"],
  "risks": ["string"],
  "needsSplit": true|false,
  "splitReason": "string (optional, if needsSplit=true)",
  "proposedSubsteps": ["string (3-7 items, optional, if needsSplit=true)"]
}
```

### 3. Split Check (Before Execution)

After the design merge, decide whether this step must be split into substeps:

- If `needsSplit=false` → continue to Step 4 (execution path)
- If `needsSplit=true` → validate and apply split, then skip execution and jump to Step 9 (Finalize output)

Validation rules for `proposedSubsteps`:
- Count: 3-7
- Atomic: single action each
- No overlap; correct order

If valid, apply split via `/file-op` (use `data.state.current.stepIndex` from Preflight):
- Template: `../templates/split.json`

Then go to Step 9 (Finalize) and output the split result (no execution performed).

### 4. Build Step FileOpsREQ (Execution)

Based on merged approach:
- Build `FileOpsREQ` JSON (see `~/.claude/skills/docs/protocol.md`)
- Include agreed done conditions
- Note identified risks

Key rule: Codex may modify code and artifacts needed to satisfy done conditions, but must **not** advance the step to `done` until Claude approves in Review.

### 5. Send FileOpsREQ (FileOps)

Send the constructed FileOpsREQ via `/file-op`:

```
/file-op <the FileOpsREQ JSON>
```

(`/file-op` handles routing to Codex via `ask --async codex`)

### 6. Execute (Executor Routing)

- If `executor == "codex"`:
  - Codex directly executes FileOpsREQ operations and returns FileOpsRES.
- If `executor == "opencode"`:
  - Codex uses the canonical `ask` skill to call the configured OpenCode agent.
  - Codex acts as supervisor:
    - Translate FileOpsREQ ops into OpenCode-friendly instructions
    - Guide OpenCode step-by-step to apply changes and run commands
    - Review OpenCode results and validate against done conditions
    - If fixes are needed, guide OpenCode to iterate (respect `constraints.max_attempts`)
  - Codex returns the final FileOpsRES (JSON only) back to Claude.

### 7. Handle FileOpsRES (Codex or OpenCode)

**status = ok** → Go to Review

**status = ask** → Show questions to user → Re-run

**status = fail** → Request `autoflow_state_mark_blocked` with `fail.reason` → Stop

Note: `status = split` should be handled by Step 3 (Split Check). Treat unexpected `split` here as `fail` and re-run design to decide `needsSplit`.

### 8. Review (Claude + Cross-Review)

Invoke `/review` skill:

```
/review step
  target: [step title]
  doneConditions: [from design output]
  changedFiles: [from FileOpsRES]
  proof: [execution summary]
```

See `../../review/references/flow.md` for full flow (Claude assessment → role-routed cross-review → Final decision).

Output: Review result with verdict (PASS/FIX/BLOCKED).

### 8.5 Test (Optional)

**Claude decides whether testing is needed** based on step nature:
- Code changes → usually needs testing
- Config/doc changes → usually not
- Refactoring → needs regression testing

If testing is needed, send test task to Codex:

```
Bash(ask --async codex "Run tests for this change:

Step: [step title]
Changed files: [list]
Test scope: [unit/integration/e2e]

Execute relevant tests and report:
1. Test command(s) executed
2. Pass/Fail summary
3. Any failures with details", run_in_background=true)
```

**Claude reviews test results**:
- All pass → Continue to Finalize
- Failures → Analyze cause, decide:
  - Fix issue (Back to step 5 with fix)
  - Mark as known issue (Continue with note)
  - Block (Mark blocked)

**Final Decision** (based on Review + Test):
- Both PASS → Finalize
- Either FIX → Merge fix items → Back to step 5 (max 1 retry)
- Disagreement → Claude makes final call with explanation

### 9. Finalize (Codex)

If Step 3 applied a split (`needsSplit=true`):
- Output: `Split applied. Next: first substep. Use /tr (autoloop will trigger if running).`
- Do not mark the step `done` (no execution happened yet).

If PASS (execution path), ask Codex to:
1) mark current step/substep `status: "done"` and advance `current`
2) regenerate `.ccb/todo.md` from `.ccb/state.json`
3) append completion entry to `.ccb/plan_log.md`

Send `FileOpsREQ` with `purpose: "finalize_step"` via `/file-op`. Codex returns `FileOpsRES` JSON only.

Auto-loop requirement (reliable next-step trigger):
- After finalizing, Codex must run the auto-loop trigger (see `autoflow_auto_loop` in `~/.claude/skills/docs/protocol.md`; implemented as an explicit `run` op).
- If there are remaining steps, it must trigger the next `/tr` automatically.
- It must be executed via the FileOpsREQ protocol (no manual copy/paste).

Recommended: combine finalize + auto-loop in one request (ops execute in order):
- Template: `../templates/finalize.json`

Output result:
- If more steps: `Step N complete. Next: [title]. Use /tr`
- If all done: `Task complete!` + acceptance checklist → Continue to Step 10 (Final Review)

### 10. Final Review (Task Completion Only)

Triggered when Step 9 Finalize detects all steps completed (`current.type == 'none'`).

#### 10.1 Full Task Review

Invoke `/review` skill with task mode:

```
/review task
  target: [task name from state.json]
  doneConditions: [acceptance criteria]
  changedFiles: [all files changed during task]
  proof: [all step summaries]
```

See `../../review/references/flow.md` for full flow.

Output: Task-level review result.

#### 10.2 Issue Handling

Based on review results:

- **No issues** → Go to 10.3 Summary Report
- **Minor issues** (typo, minor fix) → Have Codex fix directly, optionally re-test, then go to 10.3
- **Medium issues** (need 1-2 extra steps) → Append steps to current task:
  1. Claude designs 1-2 fix steps
  2. Call `/file-op` to append steps to `.ccb/state.json`:
     - Template: `../templates/append-steps.json`
  3. Continue executing `/tr` to complete appended steps
  4. After completion, re-enter Step 10
- **Large issues** (need >2 steps) → Create follow-up task:
  1. Record unresolved issues in final report
  2. Prompt user: "Found N larger issues, suggest creating new task: /tp [follow-up description]"
  3. Go to 10.3 to complete current task report
- **Unreasonable requirement** → Record reason, skip fix, go to 10.3

#### 10.3 Summary Report

Claude plans report structure and generates `reportContent`:
- `documenter = "codex"` (default): Claude generates `reportContent` directly
- `documenter = "gemini"`: Claude calls `/ask gemini` to generate `reportContent` (markdown), then has Codex write the file

Codex writes `reportContent` to `final/` folder:

- Template: `../templates/final-report.json`

**Report structure**:
- Task Overview
- Implementation Summary
- Steps Executed
- Key Decisions
- Issues Encountered & Resolutions
- Final Verification Results
- Recommendations (if any)

---

## Principles

1. **Shortest path**: Execute directly, split only when necessary
2. **Binary review**: PASS or FIX, no scoring
3. **Limited iterations**: Max 2 per step
4. **Auto-advance**: State transitions via file updates
