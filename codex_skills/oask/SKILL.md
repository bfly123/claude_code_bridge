---
name: oask
description: Async via oask, end turn immediately; use only when user explicitly delegates to OpenCode (ask/@opencode/let opencode/review); NOT for questions about OpenCode itself.
---

# Ask OpenCode (Async)

Send the user's request to OpenCode asynchronously.

## Execution (MANDATORY)

```
Bash(oask <<'EOF'
$ARGUMENTS
EOF
, run_in_background=true)
```

## CRITICAL Rules

- Always use `run_in_background=true`.
- After running `oask`, say "OpenCode processing (task: xxx)" and immediately end your turn.
- Do not wait for results or check status in the same turn.
