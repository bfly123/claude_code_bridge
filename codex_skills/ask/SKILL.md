---
name: ask
description: Send a request to a CCB agent with `ask`. Default async; use wait only when the user explicitly wants the reply now.
metadata:
  short-description: Ask agent
---

Use this skill when the user writes `$ask`.

Syntax:

```text
$ask <target> <message...>
```

Rules:

- `TARGET` is the first token after `$ask`.
- `MESSAGE` is the exact raw remainder after `TARGET`.
- If `MESSAGE` is empty, stop and report a short usage error.
- Forward `MESSAGE` verbatim. Do not rewrite, summarize, or translate it.
- Sender is inferred from the current CCB workspace.
- Use `TARGET=all` for broadcast. Do not expand the recipient list yourself.
- Do not inspect files, search the repo, explain a plan, or add commentary first.
- Default behavior is async submit.
- Only use `--wait` if the user explicitly asks to wait for the reply in the same turn.
- Only use `--silence` if the user explicitly asks for silent success mail.
- Do not run `pend`, `ping`, `watch`, retries, or any follow-up command unless the user explicitly asks.

Default:

```bash
command ask "$TARGET" <<'EOF'
$MESSAGE
EOF
```

Wait:

```bash
command ask --wait "$TARGET" <<'EOF'
$MESSAGE
EOF
```

Silent:

```bash
command ask --silence "$TARGET" <<'EOF'
$MESSAGE
EOF
```

Wait + silent:

```bash
command ask --wait --silence "$TARGET" <<'EOF'
$MESSAGE
EOF
```

If async output contains `[CCB_ASYNC_SUBMITTED ...]`, stop immediately and return that output only.
