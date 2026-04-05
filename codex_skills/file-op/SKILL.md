---
name: file-op
description: Execute FileOpsREQ protocol requests. Handles autoflow domain ops for .ccb/ state management.
---

# FileOps Executor (Codex Side)

You receive FileOpsREQ JSON from Claude and must return FileOpsRES JSON only. No markdown, no prose.

## Protocol Reference

See `~/.claude/skills/docs/protocol.md` for full FileOpsREQ/FileOpsRES schema.

## Execution Rules

1. Parse the incoming FileOpsREQ JSON
2. Validate against schema (proto, id, purpose, ops, done, report)
3. Execute each op in order
4. Return FileOpsRES JSON only

## AutoFlow Domain Ops Implementation

All state files live under `.ccb/` directory relative to repo root.

### `autoflow_plan_init`

Input: `plan` object with taskName, objective, context, constraints, steps[], finalDone[]

Actions:
1. Create `.ccb/` directory if not exists
2. Build `state.json` from plan:
   ```json
   {
     "taskName": plan.taskName,
     "objective": plan.objective,
     "context": plan.context,
     "constraints": plan.constraints,
     "current": { "type": "step", "stepIndex": 1, "subIndex": null },
     "steps": [ { "index": i+1, "title": title, "status": "todo" (first="doing"), "attempts": 0, "substeps": [] } ],
     "finalDone": plan.finalDone
   }
   ```
3. Write `.ccb/state.json`
4. Generate `.ccb/todo.md` from state (see formats.md)
5. Generate `.ccb/plan_log.md` with initial plan entry

### `autoflow_state_preflight`

Input: `path` (default `.ccb/state.json`), `maxAttempts` (default 2)

Actions:
1. Read `.ccb/state.json`
2. If file missing → return fail status with "No plan. Use /tp first."
3. Validate `current` pointer
4. If `current.type == "none"` → return ok with taskComplete flag
5. Get current step/substep, check attempts < maxAttempts
6. If attempts exceeded → return fail with "Max attempts exceeded"
7. Increment attempts, write back `.ccb/state.json`
8. Return ok with `data.state` (current pointer) and `data.stepContext` (step title, objective, relevant info)

### `autoflow_state_apply_split`

Input: `stepIndex`, `substeps` (array of 3-7 title strings)

Actions:
1. Read `.ccb/state.json`
2. Find step by stepIndex
3. Set step.substeps = substeps mapped to `{ index: i+1, title: t, status: "todo" }`, first one "doing"
4. Set `current = { type: "substep", stepIndex: stepIndex, subIndex: 1 }`
5. Write `.ccb/state.json`
6. Regenerate `.ccb/todo.md`

### `autoflow_state_finalize`

Input: `verification` (string), `changedFiles` (optional array)

Actions:
1. Read `.ccb/state.json`
2. Mark current step/substep status = "done"
3. Advance `current` to next todo step/substep:
   - If substeps remain in current step → next substep
   - If no substeps remain → next step
   - If no steps remain → set `current = { type: "none", stepIndex: null, subIndex: null }`
4. If next item exists, set its status to "doing"
5. Write `.ccb/state.json`
6. Regenerate `.ccb/todo.md`
7. Append completion entry to `.ccb/plan_log.md`

### `autoflow_state_mark_blocked`

Input: `reason` (string)

Actions:
1. Read `.ccb/state.json`
2. Mark current step/substep status = "blocked"
3. Write `.ccb/state.json`
4. Regenerate `.ccb/todo.md`

### `autoflow_state_append_steps`

Input: `steps` (array of 1-2 title strings), `maxAllowed` (default 2)

Precondition: `current.type == "none"` (task completed)

Actions:
1. Read `.ccb/state.json`
2. If steps.length > maxAllowed → return fail
3. Append new steps to steps array
4. Set `current` to first new step, mark it "doing"
5. Write `.ccb/state.json`
6. Regenerate `.ccb/todo.md`
7. Append to `.ccb/plan_log.md`

## Output Format

Always return pure JSON matching FileOpsRES schema. Never wrap in markdown code blocks.
