---
name: cask
description: Async via cask, end turn immediately; use only when user explicitly delegates to Codex (ask/@codex/let codex/review); NOT for questions about Codex itself.
metadata:
  short-description: Ask Codex asynchronously via cask
  managed-by: ccb-installer
  template-variant: bash
---

# Ask Codex (Async)

Send the user’s request to Codex asynchronously.

## Execution (MANDATORY)

```
Bash(cask <<'EOF'
$ARGUMENTS
EOF
, run_in_background=true)
```

## Rules

- After running `cask`, say “Codex processing...” and immediately end your turn.
- Do not wait for results or check status in the same turn.

## Notes

- If it fails, check backend health with `cping`.
