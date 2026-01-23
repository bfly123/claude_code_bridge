---
name: curpend
description: Retrieve the latest Cursor task result using curpend.
metadata:
  short-description: View Cursor task result
---

# View Cursor Result

Retrieve the latest result from a Cursor Agent task.

## Execution (MANDATORY)

```
Bash(curpend)
```

## Options

- `curpend --task-id <id>` - Retrieve specific task by ID
- `curpend --raw` - Output raw JSON metadata

## Notes

- Shows task status, chat ID (for resume), and reply content
- Chat ID can be used with `curask --resume <chatId>` to continue session
