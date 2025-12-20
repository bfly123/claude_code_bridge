Forward commands to Gemini session and wait for reply via `gask-w` command (supports tmux / WezTerm).

Execution:
- Run `Bash(gask-w "<content>")`
- After sending, STOP immediately and wait for user input
- Do NOT continue with other tasks

Parameters:
- `<content>` required, will be forwarded to Gemini session

Workflow:
1. Send to Gemini and wait for reply
2. Display result to user
3. STOP and wait for user's next instruction

Examples:
- `Bash(gask-w "explain this code")` -> wait for reply, then STOP

Hints:
- Use `/gpend` to view latest reply
- Use `gask` for fire-and-forget (no wait)
