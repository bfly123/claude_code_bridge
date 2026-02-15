---
name: ask
description: Async via ask, end turn immediately; use when user explicitly delegates to any AI provider (gemini/codex/opencode/droid); NOT for questions about the providers themselves.
metadata:
  short-description: Ask AI provider asynchronously
---

# Ask AI Provider (Async)

Send the user's request to specified AI provider asynchronously.

## Usage

The first argument must be the provider name, followed by the message:
- `gemini` - Send to Gemini
- `codex` - Send to Codex
- `opencode` - Send to OpenCode
- `droid` - Send to Droid

## Execution (MANDATORY)

```
Bash(CCB_CALLER=claude ask $PROVIDER "$MESSAGE")
```

## Rules

- Follow the **Async Guardrail** rule in CLAUDE.md (mandatory).
- Local fallback: if output contains `CCB_ASYNC_SUBMITTED`, end your turn immediately.
- If submit fails (non-zero exit):
  - Reply with exactly one line: `[Provider] submit failed: <short error>`
  - End your turn immediately.

## Examples

- `/ask gemini What is 12+12?`
- `/ask codex Refactor this code`
- `/ask opencode Analyze this bug`
- `/ask droid Execute this task`

## Notes

- `ask` already runs in background by default; no manual `nohup` is needed.
- If it fails, check backend health with the corresponding ping command (`ccb-ping <provider>` (e.g., `ccb-ping gemini`)).
