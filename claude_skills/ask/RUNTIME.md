# Async Ask

Use this only for `/ask`.

Rules:

- Default `/ask` is asynchronous.
- Submit with `ask`.
- Sender is inferred from the current CCB workspace.
- Use `TARGET=all` for broadcast.
- After successful async submit, end the current turn immediately.
- If output contains `[CCB_ASYNC_SUBMITTED ...]`, the handoff is complete for this turn.
- Do not say you are waiting for replies.
- Do not summarize recipient lists after async submit.
- Do not run `pend`, `ping`, `watch`, retries, or any follow-up command unless the user explicitly asks.
- Do not use `--wait` unless the user explicitly asks to wait in the same turn.

Execution:

```bash
command ask "$TARGET" <<'EOF'
$MESSAGE
EOF
```

Failure handling:

- If submit fails, report the command failure briefly and stop.
