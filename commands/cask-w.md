Forward commands to Codex session and wait for reply via `cask-w` command (supports tmux / WezTerm, forward only, does not execute in current Claude process).

Execution:
- Run `Bash(cask-w "<content>")`
- After sending, STOP immediately and wait for user input
- Do NOT continue with other tasks

Parameters:
- `<content>` required, will be forwarded to Codex session

Workflow:
1. Send to Codex and wait for reply
2. Display result to user
3. STOP and wait for user's next instruction

Examples:
- `Bash(cask-w "1+2")` -> wait for reply, then STOP

Hints:
- Use `/cpend` to view latest reply
- Use `cask` for fire-and-forget (no wait)
