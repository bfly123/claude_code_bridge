---
name: gask
description: Async via gask, end turn immediately; use only when user explicitly delegates to Gemini (ask/@gemini/let gemini/review); NOT for questions about Gemini itself.
metadata:
  short-description: Ask Gemini asynchronously via gask
---

# Ask Gemini (Async)

Send the user’s request to Gemini asynchronously.

## Execution (MANDATORY)

```
Bash(gask <<'EOF'
$ARGUMENTS
EOF
, run_in_background=true)
```

## Rules

- After running `gask`, say “Gemini processing...” and immediately end your turn.
- Do not wait for results or check status in the same turn.

## Notes

- If it fails, check backend health with `gping`.
