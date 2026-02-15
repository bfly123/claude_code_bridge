# Changelog

## Unreleased

## v5.2.5 (2026-02-15)

### 🔧 Bug Fixes

- **Async Guardrail**: Added global mandatory turn-stop rule to `claude-md-ccb.md` to prevent Claude from polling after async `ask` submission
- **Marker Consistency**: `bin/ask` now emits `[CCB_ASYNC_SUBMITTED provider=xxx]` matching all other provider scripts
- **SKILL.md DRY**: Ask skill rules reference global guardrail with local fallback, eliminating duplicate maintenance
- **Command References**: Fixed `/ping` → `/cping` and `ping` → `ccb-ping` in docs

## v5.2.4 (2026-02-11)

### 🔧 Bug Fixes

- **Explicit CCB_CALLER**: `bin/ask` no longer defaults to `"claude"` when `CCB_CALLER` is unset; exits with an error instead
- **SKILL.md template**: Ask skill execution template now explicitly passes `CCB_CALLER=claude`

## v5.2.3 (2026-02-09)

### 🚀 Project-Local History + Legacy Compatibility

- **Local History**: Context exports now save to `./.ccb/history/` per project
- **CWD Scope**: Auto transfer runs only for the current working directory
- **Legacy Migration**: Auto-detect `.ccb_config` and upgrade to `.ccb` when possible
- **Claude /continue**: Attach the latest history file with a single skill

## v5.2.2 (2026-02-04)

### 🚀 Session Switch Capture

- **Old Session Fields**: `.claude-session` now records `old_claude_session_id` / `old_claude_session_path` with `old_updated_at`
- **Auto Context Export**: Previous Claude session is extracted to `./.ccb/history/claude-<timestamp>-<old_id>.md`
- **Transfer Cleanup**: Improved noise filtering while preserving tool-only actions

## v5.1.2 (2026-01-29)

### 🔧 Bug Fixes & Improvements

- **Claude Completion Hook**: Unified askd now triggers completion hook for Claude
- **askd Lifecycle**: askd is bound to CCB lifecycle to avoid stale daemons
- **Mounted Detection**: `ccb-mounted` now uses ping-based detection across all platforms
- **State File Lookup**: `askd_client` falls back to `CCB_RUN_DIR` for daemon state files

## v5.1.1 (2025-01-28)

### 🔧 Bug Fixes & Improvements

- **Unified Daemon**: All providers now use unified askd daemon architecture
- **Install/Uninstall**: Fixed installation and uninstallation bugs
- **Process Management**: Fixed kill/termination issues

### 🔧 ask Foreground Defaults

- `bin/ask`: Foreground mode available via `--foreground`; `--background` forces legacy async
- Managed Codex sessions default to foreground to avoid background cleanup
- Environment overrides: `CCB_ASK_FOREGROUND=1` / `CCB_ASK_BACKGROUND=1`
- Foreground runs sync and suppresses completion hook unless `CCB_COMPLETION_HOOK_ENABLED` is set
- `CCB_CALLER` now defaults to `codex` in Codex sessions when unset

## v5.1.0 (2025-01-26)

### 🚀 Major Changes: Unified Command System

**New unified commands replace provider-specific commands:**

| Old Commands | New Unified Command |
|--------------|---------------------|
| `cask`, `gask`, `oask`, `dask`, `lask` | `ask <provider> <message>` |
| `cping`, `gping`, `oping`, `dping`, `lping` | `ccb-ping <provider>` (skill: `/cping`) |
| `cpend`, `gpend`, `opend`, `dpend`, `lpend` | `pend <provider> [N]` |

**Supported providers:** `gemini`, `codex`, `opencode`, `droid`, `claude`

### 🪟 Windows WezTerm + PowerShell Support

- Full support for Windows native environment with WezTerm terminal
- `install.ps1` now generates wrappers for `ask`, `ccb-ping`, `pend`, `ccb-completion-hook`
- Background execution uses PowerShell scripts with `DETACHED_PROCESS` flag
- WezTerm CLI integration with stdin for large payloads (avoids command line length limits)
- UTF-8 BOM handling for PowerShell-generated session files

### 🔧 Technical Improvements

- `completion_hook.py`: Uses `sys.executable` for cross-platform script execution
- `ccb-completion-hook`:
  - Added `find_wezterm_cli()` with PATH lookup and common install locations
  - Support `CCB_WEZTERM_BIN` environment variable
  - Uses stdin for WezTerm send-text to handle large payloads
- `bin/ask`:
  - Unix: Uses `nohup` for true background execution
  - Windows: Uses PowerShell script + message file to avoid escaping issues
- Added `SKILL.md.powershell` for `cping` and `pend` skills

### 📦 Skills System

New unified skills:
- `/ask <provider> <message>` - Async request to AI provider
- `/cping <provider>` - Test provider connectivity
- `/pend <provider> [N]` - View latest provider reply

### ⚠️ Breaking Changes

- Old provider-specific commands (`cask`, `gask`, etc.) are deprecated
- Old skills (`/cask`, `/gask`, etc.) are removed
- Use new unified commands instead

### 🔄 Migration Guide

```bash
# Old way
cask "What is 1+1?"
gping
cpend

# New way
ask codex "What is 1+1?"
ccb-ping gemini
pend codex
```

---

For older versions, see [CHANGELOG_4.0.md](CHANGELOG_4.0.md)
