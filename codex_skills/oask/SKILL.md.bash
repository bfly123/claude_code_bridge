---
name: oask
description: Send a task to OpenCode via the `oask` CLI and wait for the reply. Use only when the user explicitly delegates to OpenCode (ask/@opencode/let opencode/review); not for questions about OpenCode itself.
metadata:
  short-description: Ask OpenCode (wait for reply) via oask
  backend: opencode
  managed-by: ccb-installer
  template-variant: bash
---

# oask (Ask OpenCode)

Use `oask` to forward the user's request to the OpenCode pane.

## Prereqs (Backend)

- `oping` should succeed.
- `oask` must run in the same environment as `ccb` (WSL vs native Windows).

## Execution (MANDATORY)

```bash
oask --sync -q <<'EOF'
$ARGUMENTS
EOF
```

## Workflow (Mandatory)

1. Ensure OpenCode backend is up (`oping`).
2. Run the command above with the user's request.
3. **IMPORTANT**: Use `timeout_ms: 3600000` (1 hour) to allow long-running tasks.
4. DO NOT send a second request until the current one exits.

## CRITICAL: Wait Silently (READ THIS)

After running `oask`, you MUST:
- **DO NOTHING** while waiting for the command to return
- **DO NOT** check status, monitor progress, or run any other commands
- **DO NOT** read files, search code, or do "useful" work while waiting
- **DO NOT** output any text like "waiting..." or "checking..."
- **JUST WAIT** silently until oask returns with the result

The command may take 10-60 minutes. This is NORMAL. Be patient.

If you find yourself wanting to do something while waiting, STOP. Just wait.

## Notes

- Always use `--sync` flag when calling from Codex.
- Do not use `--async` from Codex: it returns immediately (no output), which causes the next task to be sent before the previous one completes.
