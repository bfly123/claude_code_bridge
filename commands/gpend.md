Use `gpend` to fetch latest reply from Gemini session, suitable for async mode or follow-up queries after timeout.

Trigger conditions (any match):
- User mentions gpend/Gpend
- User wants to view/fetch/get Gemini reply/response
- User asks for recent N Gemini conversations/replies (e.g. "调取最近5条gemini回复", "show last 3 gemini messages")

Execution:
- `gpend` - fetch latest single reply: `Bash(gpend)`
- `gpend N` - fetch last N conversations (Q&A pairs): `Bash(gpend N)` (e.g. `gpend 5`)
- Keep command execution silent, no additional analysis after execution

Output format (when N > 1):
```
Q: user question 1
A: gemini reply 1
---
Q: user question 2
A: gemini reply 2
```

Common scenarios:
- View reply after gask async send
- Continue getting reply after gask-w timeout
- Review recent conversation history with Gemini

Hints:
- If command returns empty, first confirm Gemini session is still running (use `/gping` to check)
