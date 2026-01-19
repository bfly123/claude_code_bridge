---
name: oping
description: "Test connectivity with OpenCode (shorthand: oc) via the `oping` CLI. Use when the user explicitly asks to check OpenCode/oc status/connection (e.g. \"oc ping\", \"oc 还活着吗\", \"OpenCode 连上没\"), or when troubleshooting OpenCode not responding."
---

# Oping

## Workflow (Mandatory)

1. Run `oping` (no extra analysis or follow-up actions).
2. Return stdout to the user.

## Notes

- If `oping` fails, ensure it runs in the same environment as `ccb` (WSL vs native Windows).
