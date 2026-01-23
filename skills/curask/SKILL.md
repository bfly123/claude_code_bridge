---
name: curask
description: Async via curask, end turn immediately; use when user explicitly delegates to Cursor.
metadata:
  short-description: Ask Cursor Agent asynchronously via curask
---

# Ask Cursor (Async)

Send the user's request to Cursor Agent asynchronously.

## Execution (MANDATORY)

```
Bash(curask <<'EOF'
$ARGUMENTS
EOF
, run_in_background=true)
```

## Rules

- After running `curask`, say "Cursor processing..." and immediately end your turn.
- Do not wait for results or check status in the same turn.

## Notes

- `--force` enabled by default (allows file editing)
- Use `curask --no-force` for read-only queries
- Use `curask --resume <chatId>` to continue a previous session
- If it fails, check backend health with `curping`.
