## Execution (MANDATORY)

```bash
command ask "$TARGET" <<'EOF'
$MESSAGE
EOF
```

This returns only an acceptance receipt in the current turn.
The reply is not echoed into the same command stdout.
Use `ask --wait "$TARGET"` only when the user explicitly wants the reply now.

## Rules

- Parse only the first token as target; send the entire remainder verbatim as the message.
- After running the command, end your turn immediately.
- Use `--wait` only when the user explicitly wants the reply in the same turn.
- The task ID and log file path will be displayed for tracking.

## Examples

- `/ask agent1 What is 12+12?` (send via heredoc)
- `command ask agent1 <<'EOF'`
  `What is 12+12?`
  `EOF`

## Notes

- If it fails, report the command failure output and stop.
