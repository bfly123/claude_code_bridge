---
name: ask
description: Send a request to a CCB agent with `ask`. Default async; use wait only when the user explicitly wants the reply now.
metadata:
  short-description: Ask agent
---

Use this only for `/ask`.

## Usage

```text
/ask <target> <message...>
```

## Rules

- `TARGET` is the first token after `/ask`.
- `MESSAGE` is the exact raw remainder after `TARGET`.
- If `MESSAGE` is empty, stop and return a brief usage error.
- Forward `MESSAGE` verbatim. Do not rewrite, summarize, translate, or paraphrase it.
- Sender is inferred from the current CCB workspace.
- Use `TARGET=all` for broadcast. Do not expand the recipient list yourself.
- Pass `MESSAGE` via stdin. Do not pass it as CLI arguments.
- Default behavior is async submit.
- Use `--wait` only if the user explicitly asks for the reply in the same turn.
- Use `--silence` only if the user explicitly asks for silent success mail.
- Do not run `pend`, `ping`, `watch`, retries, or any follow-up command unless the user explicitly asks.
- Do not add commentary before submit. After async submit, return the command output only.

## Execution

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

## Completion

- If output contains `[CCB_ASYNC_SUBMITTED ...]`, stop immediately and return that output only.
- If submit fails, report the command failure output briefly and stop.

## Examples

- `/ask agent1 1+1=?`
- `/ask agent2 Summarize this diff`
- `/ask all 请同步检查当前方案`
