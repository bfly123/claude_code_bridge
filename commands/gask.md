Send message to Gemini and wait for reply via `gask` (sync mode).

Designed for Claude Code: run with `run_in_background=true` so Claude can continue working while Gemini processes.

Foreground sync (when user explicitly requests): use `gask-w`.

Workflow:
1. Run `Bash(gask "<content>", run_in_background=true)` to start background task
2. Tell user "Gemini processing (task: xxx)" then IMMEDIATELY END your turn (IMPORTANT)
   DO NOT wait for result or continue working
3. When bash-notification arrives, show the task output

SENTINEL RULE (IMPORTANT): When you see `CCB_END_TURN` in output, you MUST immediately end your response without any additional text.

Parameters:
- `<content>` required
- `--timeout SECONDS` optional (default from `CCB_SYNC_TIMEOUT`, fallback 3600)
- `--output FILE` optional: write reply atomically to FILE (stdout stays empty)

Output contract:
- stdout: reply text only (or empty when `--output` is used)
- stderr: progress/errors
- exit code: 0 = got reply, 2 = timeout/no reply, 1 = error
