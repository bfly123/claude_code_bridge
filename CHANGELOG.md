# Changelog

## Unreleased

## v6.0.2 (2026-04-17)

### 🔁 Agent Routing & Install Guardrails

- **Caller Attribution Fix**: `ccb ask` now preserves the originating agent identity so replies route back to the correct mailbox instead of drifting to `user` or `cmd`
- **Mailbox Delivery Stability**: control-plane reply routing now keeps async `cmd` mailbox delivery aligned with the real caller chain
- **Mixed-Case Agent Recovery**: config layout recovery now normalizes mixed-case agent names consistently during restore and startup
- **macOS Dependency Warning**: `install.sh` now warns when Homebrew is missing on macOS before tmux and related dependencies are installed

## v6.0.1 (2026-04-16)

### 🔧 Release Hygiene & Upgrade Safety

- **Tracked Temp Cleanup**: Removed accidentally tracked `.tmp_pytest` artifacts that contaminated GitHub source archives
- **Repo Hygiene Guard**: Added a regression test to block ephemeral test artifacts from entering the git index again
- **Safer Tar Validation**: Upgrade/install extraction now rejects unsafe symlink targets before unpacking
- **Clearer Extraction Errors**: Unsafe archive failures now explain that the archive contains unsafe paths or links and should be replaced with a clean source archive or official release asset

## v6.0.0 (2026-04-16)

### 🚀 Multi-Agent Runtime

- **Infinite Parallel Agent Edition**: CCB v6 establishes the runtime foundation for effectively unbounded multi-agent delegation inside one project
- **Independent Agent Identity**: Each agent can carry its own role, task stream, skill set, and collaboration style
- **Stable Native Communication**: Agent-to-agent orchestration continues through the built-in control plane instead of shell-level glue

### 🧭 Public CLI Surface

- **User Workflow Reduced**: Public startup and rebuild flow is now intentionally centered on `ccb`, `ccb -s`, `ccb -n`, `ccb kill`, and `ccb kill -f`
- **Control Plane Retained**: `ask`, `ping`, `pend`, and `watch` remain available for model-side coordination without dominating user help
- **Safe Rebuild Semantics**: Legacy project runtime state is rebuilt from `.ccb/ccb.config`, while current 6.x projects retain an explicit runtime marker

### 🌳 Workspace & Recovery

- **Default Inplace Workspaces**: Agents now default to `inplace`; isolated branches are opt-in via `agent:provider(worktree)`
- **Worktree Reconciliation**: Added stable handling for added, removed, renamed, dirty, missing, and unmerged worktree agents during start, kill, and `ccb -n`
- **Restore Stability**: Namespace root panes are preserved during cleanup so restart/restore flows no longer self-delete active project panes

### 🤖 Provider & Release Reliability

- **Gemini Multi-Round Completion**: Gemini completion polling now survives planning/tool rounds and waits for the real final reply
- **Linux Release Path**: `ccb update` for the 6.x line is now aligned to Linux/WSL release assets instead of source snapshots
- **Release Metadata Preservation**: Install/update paths preserve embedded version, commit, and date metadata, including git worktree installs

## v5.3.0 (2026-04-14)

### 🚀 CLI & Workspace Model

- **Public CLI Simplified**: User-facing startup flow is now centered on `ccb`, `ccb -s`, `ccb -n`, `ccb kill`, and `ccb kill -f`
- **Explicit Worktree Opt-In**: Compact `ccb.config` entries now default to `workspace_mode='inplace'`; isolated branches require `agent:provider(worktree)`
- **Internal Control Plane Preserved**: `ask`, `ping`, `pend`, and `watch` remain available for model-side orchestration without crowding the main user help

### 🔧 Project State Recovery

- **Reset Rebuilds Cleanly**: `ccb -n` rebuilds project runtime state while preserving `.ccb/ccb.config`
- **Stale Worktree Cleanup**: Startup and reset paths now prune missing registered git worktrees before rematerializing agent workspaces
- **Agent Change Reconciliation**: Adding agents no longer disturbs existing worktrees; removing or renaming worktree agents retires clean branches and blocks on unmerged or dirty ones
- **Kill Warnings**: `ccb kill` now warns clearly when project worktree agents still have unmerged or dirty state that needs user attention

### 🤖 Completion Reliability

- **Gemini Multi-Round Stability**: Gemini completion polling now tracks tool-call activity and no longer treats the first stable planning message as the final answer
- **Detector Reset Safety**: Session rotation clears tool-active state so later turns are evaluated independently

### ✅ Regression Coverage

- Added focused tests for the simplified CLI surface, worktree reconciliation and reset/kill safeguards, and Gemini early-completion regression paths

## v5.2.8 (2026-03-07)

### 📝 Documentation

- **tmux Layout Tip**: Added English and Chinese usage notes explaining that `Ctrl+b` then `Space` cycles tmux layouts and can be pressed repeatedly

## v5.2.7 (2026-03-07)

### 🔧 Stability Fixes

- **Completion Status**: Completion hook now distinguishes `completed`, `cancelled`, `failed`, and `incomplete` instead of reporting every terminal state as completed
- **Cancellation Handling**: Gemini and Claude adapters now consistently honor cancellation and emit a terminal status instead of leaving requests stuck in processing
- **Routing Safety**: Completion routing now keeps parent-project to subdirectory compatibility while preventing nested child sessions from hijacking parent notifications
- **Codex Session Binding**: Bound Codex requests no longer drift to a newer session log in the same worktree
- **askd Startup Guardrails**: `bin/ask` now respects `CCB_ASKD_AUTOSTART=0` and scrubs inherited daemon lifecycle env before spawning askd
- **Claude Session Backfill**: `ccb` startup again backfills `work_dir` and `work_dir_norm` into existing `.claude-session` files
- **Regression Tests**: Added focused tests for completion status handling, caller routing, autostart behavior, cancellation paths, and Codex session binding

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

### 🪟 Windows Backend Direction

- The old native-Windows backend path has been removed from the active codebase
- Current Unix runtime is tmux-only
- Native Windows mux support is being redesigned around `psmux`

### 🔧 Technical Improvements

- `completion_hook.py`: Uses `sys.executable` for cross-platform script execution
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
