Use `cpend` to fetch latest reply from Codex official logs, suitable for async mode or follow-up queries after timeout.

Execution:
- Use `Bash(cpend)` on Claude side, keep command execution silent
- Run `cpend` directly in local terminal

Features:
1. Parses log path recorded in `.codex-session`, locates latest JSONL file for current session
2. Reads tail messages and returns Codex's most recent output
3. If no new content, will prompt "No Codex reply yet"

Common scenarios:
- View results after submitting multiple tasks via `cask` async
- Manually confirm if Codex has responded after `cask-w` timeout exit
- Need to verify if Codex reply matches original question

Hints:
- Log file usually located at `~/.codex/sessions/.../rollout-<session>.jsonl`
- If command returns empty, first confirm Codex session is still running (use `/cping` to check)
