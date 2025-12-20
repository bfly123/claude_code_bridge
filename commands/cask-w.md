Forward commands to Codex session and wait for reply via `cask-w` command (supports tmux / WezTerm, forward only, does not execute in current Claude process).

Execution:
- Run in background `Bash(cask-w "<content>", run_in_background=true)`
- Continue conversation immediately after sending, no blocking wait
- Use `TaskOutput(task_id, block=true)` to get result when needed

Parameters:
- `<content>` required, will be forwarded to Codex session
- Returns task_id for later result retrieval

Workflow:
1. Send to Codex in background
2. Return task_id immediately
3. Claude continues with other tasks
4. Use TaskOutput to get reply when needed

Examples:
- `Bash(cask-w "1+2", run_in_background=true)` -> returns task_id
- `TaskOutput(task_id, block=true)` -> get Codex reply

Hints:
- Can continue conversation after sending, no need to wait
- Use `/cpend` to view latest reply
- Use `TaskOutput` to get specific task result
