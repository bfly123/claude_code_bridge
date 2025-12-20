Forward commands to Gemini session and wait for reply via `gask-w` command (supports tmux / WezTerm).

Execution:
- Run in background `Bash(gask-w "<content>", run_in_background=true)`
- Continue conversation immediately after sending, no blocking wait
- Use `TaskOutput(task_id, block=true)` to get result when needed

Parameters:
- `<content>` required, will be forwarded to Gemini session
- Returns task_id for later result retrieval

Workflow:
1. Send to Gemini in background
2. Return task_id immediately
3. Claude continues with other tasks
4. Use TaskOutput to get reply when needed

Examples:
- `Bash(gask-w "explain this code", run_in_background=true)` -> returns task_id
- `TaskOutput(task_id, block=true)` -> get Gemini reply

Hints:
- Can continue conversation after sending, no need to wait
- Use `/gpend` to view latest reply
- Use `TaskOutput` to get specific task result
