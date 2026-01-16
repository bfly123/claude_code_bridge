---
name: oask
description: Async via oask, end turn immediately; use only when user explicitly delegates to OpenCode (ask/@opencode/let opencode/review); NOT for questions about OpenCode itself.
metadata:
  short-description: Ask OpenCode asynchronously via oask
---

# Ask OpenCode (Async)

Send the user’s request to OpenCode asynchronously.

## Execution (MANDATORY)

```
Bash(oask <<'EOF'
$ARGUMENTS
EOF
)
```

## CRITICAL Rules

- Always use `run_in_background=true`.
- After running `oask`, say “OpenCode processing...” and immediately end your turn.
- Do not wait for results or check status in the same turn.

## Notes

- If it fails, check backend health with `oping`, or start it with `ccb up opencode`.
- For short 1-liners you can also do: `Bash(oask "…", run_in_background=true)` (but prefer heredoc for arbitrary text).
- For a more complete pattern (including heredoc/multiline): `../docs/async-ask-pattern.md`
