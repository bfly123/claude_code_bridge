---
name: oping
description: "Test connectivity with OpenCode (shorthand: oc) via the `oping` CLI. Use when the user explicitly asks to check OpenCode/oc status/connection (e.g. \"oc ping\", \"oc 还活着吗\", \"OpenCode 连上没\"), troubleshoot OpenCode not responding, or verify `ccb up opencode` succeeded."
---

# Oping

## Workflow (Mandatory)

1. Run `oping` (no extra analysis or follow-up actions).
2. Return stdout to the user.

## Notes

- If `oping` fails, suggest starting OpenCode with `ccb up opencode` and ensure `oping` runs in the same environment as `ccb` (WSL vs native Windows).
