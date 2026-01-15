---
name: gping
description: "Test connectivity with Gemini (shorthand: g/gm) via the `gping` CLI. Use when the user explicitly asks to check Gemini/gm status/connection (e.g. \"g ping\", \"gm ping\", \"Gemini 连上没\"), or when troubleshooting Gemini not responding."
---

# gping (Ping Gemini)

## Workflow (Mandatory)

1. Run `gping` (no extra analysis or follow-up actions).
2. Return stdout to the user.

## Notes

- If `gping` fails, suggest starting Gemini with `ccb up gemini` and ensure `gping` runs in the same environment as `ccb` (WSL vs native Windows).
