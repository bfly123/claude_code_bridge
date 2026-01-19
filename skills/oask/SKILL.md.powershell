---
name: oask
description: Async via oask, end turn immediately; use only when user explicitly delegates to OpenCode (ask/@opencode/let opencode/review); NOT for questions about OpenCode itself.
metadata:
  short-description: Ask OpenCode asynchronously via oask
  managed-by: ccb-installer
  template-variant: powershell
---

# Ask OpenCode (Async)

Send the user’s request to OpenCode asynchronously.

## Execution (MANDATORY)

```
Bash(@"
$ARGUMENTS
"@ | oask, run_in_background=true)
```

## Rules

- After running `oask`, say “OpenCode processing...” and immediately end your turn.
- Do not wait for results or check status in the same turn.

## Notes

- If it fails, check backend health with `oping`.
