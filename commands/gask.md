Forward commands to Gemini session via `gask` command (supports tmux / WezTerm, forward only, does not execute in current Claude process).

Execution:
- Run silently `Bash(gask "<content>")`, no additional analysis or operations after execution
- Can also run `gask <content>` in terminal with same effect

Parameters:
- `<content>` required, will be forwarded to Gemini session
- Note: gask only forwards, does not execute in Claude process, returns immediately after

Examples:
- `Bash(gask "explain this code")`
- `Bash(gask "help me optimize this function")`

Hints:
- gask returns immediately after sending, does not wait for result
- Use `/gask-w` if you need to wait for Gemini reply
- After gask returns, forwarding is complete, no further action needed
