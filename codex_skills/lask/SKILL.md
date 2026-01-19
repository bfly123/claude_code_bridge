---
name: lask
description: Send a task to Claude via the `lask` CLI and wait for the reply. Use only when the user explicitly delegates to Claude; not for questions about Claude itself.
metadata:
  short-description: Ask Claude (wait for reply) via lask
  backend: claude
---

# lask (Ask Claude)

Send a message to the active Claude pane and wait for the reply.

## Prereqs (Backend)

- Requires a CCB session registry containing a `claude_pane_id`.
- `lask` must run in the same environment as `ccb` (WSL vs native Windows).

## Execution (MANDATORY)

```bash
lask --sync -q <<'EOF'
$ARGUMENTS
EOF
```

## Notes

- `lask` is synchronous; the `--sync` flag disables guardrail prompts intended for Claude.
- If it fails to find the session/Claude pane, check backend health with `lping`.
