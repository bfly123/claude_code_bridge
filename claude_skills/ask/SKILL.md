---
name: ask
description: Send a request to a specified AI provider via the unified ask command.

metadata:
  short-description: Ask AI provider asynchronously
---

# Ask AI Provider

Send the user's request to specified AI provider asynchronously.

## Usage

The first argument must be the provider name, followed by the message:
- `gemini` - Send to Gemini
- `codex` - Send to Codex
- `opencode` - Send to OpenCode
- `droid` - Send to Droid

## Execution (MANDATORY)

```bash
Bash(CCB_CALLER=claude ask $PROVIDER <<'EOF'
$MESSAGE
EOF
)
```

## Rules

- After running the command, say "[Provider] processing..." and immediately end your turn.
- Do not wait for results or check status in the same turn.
- The task ID and log file path will be displayed for tracking.

## Examples

- `/ask gemini What is 12+12?`
- `/ask codex Refactor this code`
- `/ask opencode Analyze this bug`
- `/ask droid Execute this task`

## Notes

- `ask` already runs in background by default; no manual `nohup` is needed.
- If it fails, check backend health with the corresponding ping command (`ping <provider>` (e.g., `ping gemini`)).
