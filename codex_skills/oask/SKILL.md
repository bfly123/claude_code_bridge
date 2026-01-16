---
name: oask
description: Send a task to OpenCode via the `oask` CLI and wait for the reply. Use only when the user explicitly delegates to OpenCode (ask/@opencode/let opencode/review); not for questions about OpenCode itself.
metadata:
  short-description: Ask OpenCode (wait for reply) via oask
  backend: opencode
---

# oask (Ask OpenCode)

Use `oask` to forward the user's request to the OpenCode pane started by `ccb up opencode`.

## Prereqs (Backend)

- `oping` should succeed; otherwise start it with `ccb up opencode`.
- `oask` must run in the same environment as `ccb` (WSL vs native Windows).

## Quick Start

- Preferred (wait & return reply): `oask -q --timeout -1 "$ARGUMENTS"`
- Multiline (optional): `oask <<'EOF'` … `EOF`

## Workflow (Mandatory)

1. Ensure OpenCode backend is up (`oping`, or run `ccb up opencode`).
2. Run `oask -q --timeout -1` with the user's request and DO NOT send a second request until it exits.

## Notes

- Do not use `--async` from Codex: it returns immediately (no output), which causes the next task to be sent before the previous one completes.
