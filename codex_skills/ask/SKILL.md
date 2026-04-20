---
name: ask
description: Send a message to a CCB agent with `ccb ask`.
metadata:
  short-description: Ask agent
---

Use this skill when the user writes `$ask`.

Syntax:

```text
$ask <target> <message...>
```

Rules:

- `target` is the first token after `$ask`.
- `message` is the exact remainder after `target`.
- If `message` is empty, stop and report a short usage error.
- Do not inspect files, search the repo, explain a plan, or add commentary first.
- Do not rewrite, summarize, or translate the message.
- Do not infer or pass a sender manually. `ccb ask` resolves it.
- Do not run `pend`, `ping`, or any follow-up command unless the user explicitly asks.
- Default behavior is async submit.
- Only use `--wait` if the user explicitly asks to wait for the reply in the same turn.
- Only use `--silence` if the user explicitly asks for silent success mail.

Default:

```bash
command ccb ask "$TARGET" <<'EOF'
$MESSAGE
EOF
```

Wait:

```bash
command ccb ask --wait "$TARGET" <<'EOF'
$MESSAGE
EOF
```

Silent:

```bash
command ccb ask --silence "$TARGET" <<'EOF'
$MESSAGE
EOF
```

Wait + silent:

```bash
command ccb ask --wait --silence "$TARGET" <<'EOF'
$MESSAGE
EOF
```

If async output contains `[CCB_ASYNC_SUBMITTED`, stop immediately and return that output only.
