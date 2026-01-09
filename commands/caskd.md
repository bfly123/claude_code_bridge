Start/stop the `caskd` daemon (Codex, WezTerm/iTerm2).

Execution:
- `Bash(caskd)` to start (runs until stopped)
- `Bash(caskd --shutdown)` to stop

Notes:
- `cask` will use `caskd` automatically when running and `CCB_CASKD=1` (default).
- `caskd` currently supports WezTerm/iTerm2 sessions only (tmux falls back to direct mode).
- State file: `~/.ccb/run/caskd.json` (override with `CCB_CASKD_STATE_FILE` / `--state-file`).
- Autostart: set `CCB_CASKD_AUTOSTART=0` (or legacy `CCB_AUTO_CASKD=0`) to disable auto-start behavior.
- Listen address: set `CCB_CASKD_LISTEN=127.0.0.1:0` (or pass `--listen host:port`).
