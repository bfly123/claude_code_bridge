Forward commands to Codex session via `cask` command (supports tmux / WezTerm, forward only, does not execute in current Claude process).

Execution:
- Run silently `Bash(cask "<content>")`, no additional analysis or operations after execution
- Can also run `cask <content>` in terminal with same effect

Parameters:
- `<content>` required, will be forwarded to Codex session (e.g. `pwd`, `ls` commands)
- Note: cask only forwards, does not execute in Claude process, returns immediately after

Examples:
- `Bash(cask "pwd")`
- `Bash(cask "ls -la")`

Hints:
- cask returns immediately after sending, does not wait for result
- Use `/cask-w` if you need to wait for Codex reply
- After cask returns, forwarding is complete, no further action needed
