---
name: lask
description: Send message to Claude pane (fire-and-forget). Use when relaying info back to Claude from Codex/Gemini/OpenCode.
---

# Send to Claude (lask)

Send a message to the active Claude pane. Does not wait for reply.

## Execution

```
Bash(lask <<'EOF'
$ARGUMENTS
EOF
)
```

## Notes

- Fire-and-forget: only sends text, does not wait for Claude's response.
- Requires CCB session registry (created by `ccb up ...`).
