# AutoFlow File-Op

Plan mode is optional. This command delegates **all repo file I/O** to Codex using the `FileOpsREQ` / `FileOpsRES` JSON protocol.

**Protocol**: See `~/.claude/skills/docs/protocol.md`

---

## Input

From `$ARGUMENTS`:
- A single `FileOpsREQ` JSON object (must include `proto: "autoflow.fileops.v1"`).

---

## Execution

1. Validate `$ARGUMENTS` is a single JSON object (no prose).
2. Send to Codex:

```
Bash(ask --async codex "Execute this FileOpsREQ JSON exactly and return FileOpsRES JSON only.\n\n## CRITICAL: Roles Self-Resolution (Hard Constraint)\nYou MUST read roles config yourself to determine executor. Do NOT rely on Claude passing constraints.executor.\n\nRoles priority (first valid wins):\n1. .autoflow/roles.json\n2. Default: executor=codex\n\nValidation: schemaVersion=1, enabled=true; otherwise skip to default.\n\n## Executor Routing\n- executor=codex (or missing): execute ops directly.\n- executor=opencode:\n  - Do NOT directly edit repo files yourself.\n  - Supervise the configured OpenCode agent via canonical `ccb ask` / `ask` to perform ALL repo-changing work (edits + mutating commands).\n  - Translate ops into clear OpenCode instructions, request execution, validate results, and iterate.\n  - Ask OpenCode to return: {changedFiles, diffSummary, commands, notes}.\n  - You MUST populate FileOpsRES.proof:\n    - proof.commands: include commands OpenCode ran (with exit codes) when applicable.\n    - proof.notes: an execution brief: changedFiles + diff summary + key decisions + test summary.\n  - If insufficient, iterate (max constraints.max_attempts or 3).\n  - Return valid FileOpsRES JSON (status ok/ask/fail/split).\n- executor=codex+opencode:\n  - Codex is the primary executor for non-mutating work (read/search/analyze/plan/review/answer).\n  - Delegate to the configured OpenCode agent via canonical `ccb ask` / `ask` ONLY when:\n    1) Repo-changing work is required (apply patches, write files, or run commands that may modify the repo/worktree), OR\n    2) Large mechanical/repetitive edits would be token-heavy for Codex (>200 lines or multi-file repetitive changes).\n  - When delegating: translate ops into clear OpenCode instructions, request execution, validate results, iterate if needed.\n  - Ask OpenCode to return: {changedFiles, diffSummary, commands, notes}.\n  - Constraint: Codex must NOT perform repo-changing work directly; all such changes must go through OpenCode.\n  - You MUST populate FileOpsRES.proof when delegating:\n    - proof.commands: include commands OpenCode ran (with exit codes).\n    - proof.notes: execution brief with changedFiles + diff summary + key decisions.\n\n$ARGUMENTS", run_in_background=true)
TaskOutput(task_id=<task_id>, block=true)
```

3. Validate the response is JSON only and matches `proto`/`id`.
4. Dispatch by `status`:
   - `ok`: return the JSON to the caller
   - `ask`: surface `ask.questions`
   - `split`: surface `split.substeps`
   - `fail`: surface `fail.reason` and stop

---

## Principles

1. **Claude never edits files**: all writes/patches happen in Codex
2. **JSON-only boundary**: request/response must be machine-parsable
3. **Prefer domain ops**: use `autoflow_*` ops for state/todo/log updates
