---
name: gask
description: Send a task to Gemini via the `gask` CLI and wait for the reply. Use only when the user explicitly delegates to Gemini (ask/@gemini/let gemini/review); not for questions about Gemini itself.
metadata:
  short-description: Ask Gemini (wait for reply) via gask
  backend: gemini
---

# gask (Ask Gemini)

Use `gask` to forward the user's request to the Gemini pane started by `ccb up gemini`.

## Prereqs (Backend)

- `gping` should succeed; otherwise start it with `ccb up gemini`.
- `gask` must run in the same environment as `ccb` (WSL vs native Windows).

## Quick Start

- Preferred (wait & return reply): `gask -q --timeout -1 "$ARGUMENTS"`
- Multiline (optional): `gask <<'EOF'` … `EOF`

## Workflow (Mandatory)

1. Ensure Gemini backend is up (`gping`, or run `ccb up gemini`).
2. Run `gask -q --timeout -1` with the user's request and DO NOT send a second request until it exits.

## Notes

- `gask` is synchronous; use `--timeout -1` to avoid premature timeouts for long Gemini runs.
