# Async Ask

Use this only for `/ask`.

Rules:

- Default `/ask` is asynchronous.
- Submit with canonical `ccb ask`.
- After successful async submit, end the current turn immediately.
- If output contains `[CCB_ASYNC_SUBMITTED ...]`, the handoff is complete for this turn.
- Do not say you are waiting for replies.
- Do not summarize recipient lists after async submit.
- Do not run `pend`, `ping`, `watch`, retries, or any follow-up command unless the user explicitly asks.
- Do not use `--wait` unless the user explicitly asks to wait in the same turn.

Execution:

```bash
command ccb ask "$TARGET" <<'EOF'
$MESSAGE
EOF
```

Broadcast:

- Use `TARGET=all`.
- Broadcast excludes the current sender agent automatically.

Failure handling:

- If submit fails, report the command failure briefly and stop.
