Use `curpend` to fetch latest result from Cursor Agent task.

WARNING: Only use when user EXPLICITLY requests. Do NOT use proactively after curask.

Trigger conditions (ALL must match):
- User EXPLICITLY mentions curpend/Curpend
- Or user asks to "view cursor reply" / "show cursor response"

Execution:
- `curpend` - fetch latest task result: `Bash(curpend)`
- `curpend --task-id <id>` - fetch specific task: `Bash(curpend --task-id <id>)`
- `curpend --raw` - output raw JSON metadata: `Bash(curpend --raw)`

Output: Shows task status, chat ID (for resume), and reply content
