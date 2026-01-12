---
name: gask
description: Async via gask, end turn immediately; use only when user explicitly delegates to Gemini (ask/@gemini/let gemini/review); NOT for questions about Gemini itself.
---

# Ask Gemini (Async)

Send the user's request to Gemini asynchronously.

## Execution (MANDATORY)

```
Bash(gask <<'EOF'
$ARGUMENTS
EOF
, run_in_background=true)
```

## CRITICAL Rules

- Always use `run_in_background=true`.
- After running `gask`, say "Gemini processing (task: xxx)" and immediately end your turn.
- Do not wait for results or check status in the same turn.
