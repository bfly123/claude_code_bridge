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

- Preferred (wait & return reply): `gask --sync -q "$ARGUMENTS"`
- Multiline (optional): `gask --sync -q <<'EOF'` … `EOF`

## Workflow (Mandatory)

1. Ensure Gemini backend is up (`gping`, or run `ccb up gemini`).
2. Run `gask --sync -q` with the user's request.
3. **IMPORTANT**: Use `timeout_ms: 3600000` (1 hour) to allow long-running tasks.
4. DO NOT send a second request until the current one exits.

## CRITICAL: Wait Silently (READ THIS)

After running `gask`, you MUST:
- **DO NOTHING** while waiting for the command to return
- **DO NOT** check status, monitor progress, or run any other commands
- **DO NOT** read files, search code, or do "useful" work while waiting
- **DO NOT** output any text like "waiting..." or "checking..."
- **JUST WAIT** silently until gask returns with the result

The command may take 10-60 minutes. This is NORMAL. Be patient.

If you find yourself wanting to do something while waiting, STOP. Just wait.

## Notes

- Always use `--sync` flag when calling from Codex.
- `gask` is synchronous; the `--sync` flag disables guardrail prompts intended for Claude.
