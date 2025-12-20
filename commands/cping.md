Use `cping` to check if current Codex session is healthy, quickly locate communication issues.

Execution:
- Run `Bash(cping)` on Claude side, no need to output command execution process
- Run `cping` directly in local terminal

Detection items:
1. Is `.codex-session` marked as active, does runtime directory exist
2. tmux mode: Is FIFO pipe still accessible
3. tmux mode: Is Codex side process alive (verified by `codex.pid`)
4. WezTerm mode: Does pane still exist (detected via `wezterm cli list`)

Output:
- Success: `Codex connection OK (...)`
- Failure: Lists missing components or error info for further troubleshooting

Hints:
- If detection fails, try re-running `ccb up codex` or check bridge logs
- On multiple timeouts or no response, run `cping` first before deciding to restart session
