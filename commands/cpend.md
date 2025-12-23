Use `cpend` to fetch latest reply from Codex official logs, suitable for async mode or follow-up queries after timeout.

Trigger conditions (any match):
- User mentions cpend/Cpend
- User wants to view/fetch/get Codex reply/response
- User asks for recent N Codex conversations/replies (e.g. "调取最近5条codex回复", "show last 3 codex messages")

Execution:
- `cpend` - fetch latest single reply: `Bash(cpend)`
- `cpend N` - fetch last N conversations (Q&A pairs): `Bash(cpend N)` (e.g. `cpend 5`)
- Keep command execution silent, no additional analysis after execution

Output format (when N > 1):
```
Q: user question 1
A: codex reply 1
---
Q: user question 2
A: codex reply 2
```

Features:
1. Parses log path recorded in `.codex-session`, locates latest JSONL file for current session
2. Reads tail messages and returns Codex's most recent output
3. If no new content, will prompt "No Codex reply yet"
4. Supports fetching last N conversations with Q&A pairs

Common scenarios:
- View results after submitting multiple tasks via `cask` async
- Manually confirm if Codex has responded after `cask-w` timeout exit
- Need to verify if Codex reply matches original question
- Review recent conversation history with Codex

Hints:
- Log file usually located at `~/.codex/sessions/.../rollout-<session>.jsonl`
- If command returns empty, first confirm Codex session is still running (use `/cping` to check)
