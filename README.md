<div align="center">

# Claude Code Bridge (ccb) v5.2.0

**New Multi-Model Collaboration Tool via Split-Pane Terminal**
**Claude & Codex & Gemini & OpenCode & Droid**
**Ultra-low token real-time communication, unleashing full CLI power**

<p>
  <img src="https://img.shields.io/badge/Every_Interaction_Visible-096DD9?style=for-the-badge" alt="Every Interaction Visible">
  <img src="https://img.shields.io/badge/Every_Model_Controllable-CF1322?style=for-the-badge" alt="Every Model Controllable">
</p>

[![Version](https://img.shields.io/badge/version-5.2.0-orange.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/bfly123/claude_code_bridge/actions/workflows/test.yml/badge.svg)](https://github.com/bfly123/claude_code_bridge/actions/workflows/test.yml)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)]()

**English** | [Chinese](README_zh.md)

![Showcase](assets/show.png)

<details>
<summary><b>Demo animations</b></summary>

<img src="assets/readme_previews/video2.gif" alt="Any-terminal collaboration demo" width="900">

<img src="assets/readme_previews/video1.gif" alt="VS Code integration demo" width="900">

</details>

</div>

---

**Introduction:** Multi-model collaboration effectively avoids model bias, cognitive blind spots, and context limitations. However, MCP, Skills and other direct API approaches have many limitations. This project offers a new WYSIWYG solution.

## ⚡ Why ccb?

| Feature | Benefit |
| :--- | :--- |
| **🖥️ Visual & Controllable** | Multiple AI models in split-pane CLI. See everything, control everything. |
| **🧠 Persistent Context** | Each AI maintains its own memory. Close and resume anytime (`-r` flag). |
| **📉 Token Savings** | Sends lightweight prompts instead of full file history. |
| **🪟 Native Workflow** | Integrates directly into **WezTerm** (recommended) or tmux. No complex servers required. |

---

<h2 align="center">🚀 What's New</h2>

<details open>
<summary><b>v5.2.0</b> - Email Integration for Remote AI Access</summary>

**📧 New Feature: Mail Service**
- **Email-to-AI Gateway**: Send emails to interact with AI providers remotely
- **Multi-Provider Support**: Gmail, Outlook, QQ, 163 mail presets
- **Provider Routing**: Use body prefix to target specific AI (e.g., `CLAUDE: your question`)
- **Real-time Polling**: IMAP IDLE support for instant email detection
- **Secure Credentials**: System keyring integration for password storage
- **Mail Daemon**: Background service (`maild`) for continuous email monitoring

See [Mail System Configuration](#-mail-system-configuration) for setup instructions.

</details>

<details>
<summary><b>v5.1.3</b> - Tmux Claude Ask Stability</summary>

**🔧 Fixes & Improvements:**
- **tmux Claude ask**: read replies from pane output with automatic pipe-pane logging for more reliable completion

See [CHANGELOG.md](CHANGELOG.md) for full details.

</details>

<details>
<summary><b>v5.1.2</b> - Daemon & Hooks Reliability</summary>

**🔧 Fixes & Improvements:**
- **Claude Completion Hook**: Unified askd now triggers completion hook for Claude
- **askd Lifecycle**: askd is bound to CCB lifecycle to avoid stale daemons
- **Mounted Detection**: `ccb-mounted` uses ping-based detection across all platforms
- **State File Lookup**: `askd_client` falls back to `CCB_RUN_DIR` for daemon state files

See [CHANGELOG.md](CHANGELOG.md) for full details.

</details>

<details>
<summary><b>v5.1.1</b> - Unified Daemon + Bug Fixes</summary>

**🔧 Bug Fixes & Improvements:**
- **Unified Daemon**: All providers now use unified askd daemon architecture
- **Install/Uninstall**: Fixed installation and uninstallation bugs
- **Process Management**: Fixed kill/termination issues

See [CHANGELOG.md](CHANGELOG.md) for full details.

</details>

<details>
<summary><b>v5.1.0</b> - Unified Command System + Windows WezTerm Support</summary>

**🚀 Unified Commands** - Replace provider-specific commands with unified interface:

| Old Commands | New Unified Command |
|--------------|---------------------|
| `cask`, `gask`, `oask`, `dask`, `lask` | `ask <provider> <message>` |
| `cping`, `gping`, `oping`, `dping`, `lping` | `ping <provider>` |
| `cpend`, `gpend`, `opend`, `dpend`, `lpend` | `pend <provider> [N]` |

**Supported providers:** `gemini`, `codex`, `opencode`, `droid`, `claude`

**🪟 Windows WezTerm + PowerShell Support:**
- Full native Windows support with WezTerm terminal
- Background execution using PowerShell + `DETACHED_PROCESS`
- WezTerm CLI integration with stdin for large payloads
- UTF-8 BOM handling for PowerShell compatibility

**📦 New Skills:**
- `/ask <provider> <message>` - Request to AI provider (background by default)
- `/ping <provider>` - Test provider connectivity
- `/pend <provider> [N]` - View latest provider reply

See [CHANGELOG.md](CHANGELOG.md) for full details.

</details>

<details>
<summary><b>v5.0.6</b> - Zombie session cleanup + mounted skill optimization</summary>

- **Zombie Cleanup**: `ccb kill -f` now cleans up orphaned tmux sessions globally (sessions whose parent process has exited)
- **Mounted Skill**: Optimized to use `pgrep` for daemon detection (~4x faster), extracted to standalone `ccb-mounted` script
- **Droid Skills**: Added full skill set (cask/gask/lask/oask + ping/pend variants) to `droid_skills/`
- **Install**: Added `install_droid_skills()` to install Droid skills to `~/.droid/skills/`

</details>

<details>
<summary><b>v5.0.5</b> - Droid delegation tools + setup</summary>

- **Droid**: Adds delegation tools (`ccb_ask_*` plus `cask/gask/lask/oask` aliases).
- **Setup**: New `ccb droid setup-delegation` command for MCP registration.
- **Installer**: Auto-registers Droid delegation when `droid` is detected (opt-out via env).

<details>
<summary><b>Details & usage</b></summary>

Usage:
```
/all-plan <requirement>
```

Example:
```
/all-plan Design a caching layer for the API with Redis
```

Highlights:
- Socratic Ladder + Superpowers Lenses + Anti-pattern analysis.
- Availability-gated dispatch (use only mounted CLIs).
- Two-round reviewer refinement with merged design.

</details>
</details>

<details>
<summary><b>v5.0.0</b> - Any AI as primary driver</summary>

- **Claude Independence**: No need to start Claude first; Codex can act as the primary CLI.
- **Unified Control**: Single entry point controls Claude/OpenCode/Gemini.
- **Simplified Launch**: Dropped `ccb up`; use `ccb ...` or the default `ccb.config`.
- **Flexible Mounting**: More flexible pane mounting and session binding.
- **Default Config**: Auto-create `ccb.config` when missing.
- **Daemon Autostart**: `caskd`/`laskd` auto-start in WezTerm/tmux when needed.
- **Session Robustness**: PID liveness checks prevent stale sessions.

</details>

<details>
<summary><b>v4.0</b> - tmux-first refactor</summary>

- **Full Refactor**: Cleaner structure, better stability, and easier extension.
- **Terminal Backend Abstraction**: Unified terminal layer (`TmuxBackend` / `WeztermBackend`) with auto-detection and WSL path handling.
- **Perfect tmux Experience**: Stable layouts + pane titles/borders + session-scoped theming.
- **Works in Any Terminal**: If your terminal can run tmux, CCB can provide the full multi-model split experience (except native Windows; WezTerm recommended; otherwise just use tmux).

</details>

<details>
<summary><b>v3.0</b> - Smart daemons</summary>

- **True Parallelism**: Submit multiple tasks to Codex, Gemini, or OpenCode simultaneously.
- **Cross-AI Orchestration**: Claude and Codex can now drive OpenCode agents together.
- **Bulletproof Stability**: Daemons auto-start on first request and stop after idle.
- **Chained Execution**: Codex can delegate to OpenCode for multi-step workflows.
- **Smart Interruption**: Gemini tasks handle interruption safely.

<details>
<summary><b>Details</b></summary>

<div align="center">

![Parallel](https://img.shields.io/badge/Strategy-Parallel_Queue-blue?style=flat-square)
![Stability](https://img.shields.io/badge/Daemon-Auto_Managed-green?style=flat-square)
![Interruption](https://img.shields.io/badge/Gemini-Interruption_Aware-orange?style=flat-square)

</div>

<h3 align="center">✨ Key Features</h3>

- **🔄 True Parallelism**: Submit multiple tasks to Codex, Gemini, or OpenCode simultaneously. The new daemons (`caskd`, `gaskd`, `oaskd`) automatically queue and execute them serially, ensuring no context pollution.
- **🤝 Cross-AI Orchestration**: Claude and Codex can now simultaneously drive OpenCode agents. All requests are arbitrated by the unified daemon layer.
- **🛡️ Bulletproof Stability**: Daemons are self-managing—they start automatically on the first request and shut down after 60s of idleness to save resources.
- **⚡ Chained Execution**: Advanced workflows supported! Codex can autonomously call `oask` to delegate sub-tasks to OpenCode models.
- **🛑 Smart Interruption**: Gemini tasks now support intelligent interruption detection, automatically handling stops and ensuring workflow continuity.

<h3 align="center">🧩 Feature Support Matrix</h3>

| Feature | `caskd` (Codex) | `gaskd` (Gemini) | `oaskd` (OpenCode) |
| :--- | :---: | :---: | :---: |
| **Parallel Queue** | ✅ | ✅ | ✅ |
| **Interruption Awareness** | ✅ | ✅ | - |
| **Response Isolation** | ✅ | ✅ | ✅ |

<details>
<summary><strong>📊 View Real-world Stress Test Results</strong></summary>

<br>

**Scenario 1: Claude & Codex Concurrent Access to OpenCode**
*Both agents firing requests simultaneously, perfectly coordinated by the daemon.*

| Source | Task | Result | Status |
| :--- | :--- | :--- | :---: |
| 🤖 Claude | `CLAUDE-A` | **CLAUDE-A** | 🟢 |
| 🤖 Claude | `CLAUDE-B` | **CLAUDE-B** | 🟢 |
| 💻 Codex | `CODEX-A` | **CODEX-A** | 🟢 |
| 💻 Codex | `CODEX-B` | **CODEX-B** | 🟢 |

**Scenario 2: Recursive/Chained Calls**
*Codex autonomously driving OpenCode for a 5-step workflow.*

| Request | Exit Code | Response |
| :--- | :---: | :--- |
| **ONE** | `0` | `CODEX-ONE` |
| **TWO** | `0` | `CODEX-TWO` |
| **THREE** | `0` | `CODEX-THREE` |
| **FOUR** | `0` | `CODEX-FOUR` |
| **FIVE** | `0` | `CODEX-FIVE` |

</details>
</details>
</details>

---

<h3 align="center">🧠 Introducing CCA (Claude Code Autoflow)</h3>

Unlock the full potential of `ccb` with **CCA** — an advanced workflow automation system built on top of this bridge.

*   **Workflow Automation**: Intelligent task assignment and automated state management.
*   **Seamless Integration**: Native support for the v3.0 daemon architecture.

[👉 View Project on GitHub](https://github.com/bfly123/claude_code_autoflow)

**Install via CCB:**
```bash
ccb update cca
```

---

## 🚀 Quick Start

**Step 1:** Install [WezTerm](https://wezfurlong.org/wezterm/) (native `.exe` for Windows)

**Step 2:** Choose installer based on your environment:

<details open>
<summary><b>Linux</b></summary>

```bash
git clone https://github.com/bfly123/claude_code_bridge.git
cd claude_code_bridge
./install.sh install
```

</details>

<details>
<summary><b>macOS</b></summary>

```bash
git clone https://github.com/bfly123/claude_code_bridge.git
cd claude_code_bridge
./install.sh install
```

> **Note:** If commands not found after install, see [macOS Troubleshooting](#-macos-installation-guide).

</details>

<details>
<summary><b>WSL (Windows Subsystem for Linux)</b></summary>

> Use this if your Claude/Codex/Gemini runs in WSL.

> **⚠️ WARNING:** Do NOT install or run ccb as root/administrator. Switch to a normal user first (`su - username` or create one with `adduser`).

```bash
# Run inside WSL terminal (as normal user, NOT root)
git clone https://github.com/bfly123/claude_code_bridge.git
cd claude_code_bridge
./install.sh install
```

</details>

<details>
<summary><b>Windows Native</b></summary>

> Use this if your Claude/Codex/Gemini runs natively on Windows.

```powershell
git clone https://github.com/bfly123/claude_code_bridge.git
cd claude_code_bridge
powershell -ExecutionPolicy Bypass -File .\install.ps1 install
```

- The installer prefers `pwsh.exe` (PowerShell 7+) when available, otherwise `powershell.exe`.
- If a WezTerm config exists, the installer will try to set `config.default_prog` to PowerShell (adds a `-- CCB_WEZTERM_*` block and will prompt before overriding an existing `default_prog`).

</details>

### Run
```bash
ccb                    # Start providers from ccb.config (default: all four)
ccb codex gemini       # Start both
ccb codex gemini opencode claude  # Start all four (spaces)
ccb codex,gemini,opencode,claude  # Start all four (commas)
ccb -r codex gemini     # Resume last session for Codex + Gemini
ccb -a codex gemini opencode  # Auto-approval mode with multiple providers
ccb -a -r codex gemini opencode claude  # Auto + resume for all providers

tmux tip: CCB's tmux status/pane theming is enabled only while CCB is running.

Layout rule: the last provider runs in the current pane. Extras are ordered as `[cmd?, reversed providers]`; the first extra goes to the top-right, then the left column fills top-to-bottom, then the right column fills top-to-bottom. Examples: 4 panes = left2/right2, 5 panes = left2/right3.
Note: `ccb up` is removed; use `ccb ...` or configure `ccb.config`.
```

### Flags
| Flag | Description | Example |
| :--- | :--- | :--- |
| `-r` | Resume previous session context | `ccb -r` |
| `-a` | Auto-mode, skip permission prompts | `ccb -a` |
| `-h` | Show help information | `ccb -h` |
| `-v` | Show version and check for updates | `ccb -v` |

### ccb.config
Default lookup order:
- `.ccb_config/ccb.config` (project)
- `~/.ccb/ccb.config` (global)

Simple format (recommended):
```text
codex,gemini,opencode,claude
```

Enable cmd pane (default title/command):
```text
codex,gemini,opencode,claude,cmd
```

Advanced JSON (optional, for flags or custom cmd pane):
```json
{
  "providers": ["codex", "gemini", "opencode", "claude"],
  "cmd": { "enabled": true, "title": "CCB-Cmd", "start_cmd": "bash" },
  "flags": { "auto": false, "resume": false }
}
```
Cmd pane participates in the layout as the first extra pane and does not change which AI runs in the current pane.

### Update
```bash
ccb update              # Update ccb to the latest version
ccb update 4            # Update to the highest v4.x.x version
ccb update 4.1          # Update to the highest v4.1.x version
ccb update 4.1.2        # Update to specific version v4.1.2
ccb update cca          # Update CCA (Claude Code Autoflow) only
ccb uninstall           # Uninstall ccb and clean configs
ccb reinstall           # Clean then reinstall ccb
```

---

<details>
<summary><b>🪟 Windows Installation Guide (WSL vs Native)</b></summary>

> **Key Point:** `ccb/cask/cping/cpend` must run in the **same environment** as `codex/gemini`. The most common issue is environment mismatch causing `cping` to fail.

Note: The installers also install OS-specific `SKILL.md` variants for Claude/Codex skills:
- Linux/macOS/WSL: bash heredoc templates (`SKILL.md.bash`)
- Native Windows: PowerShell here-string templates (`SKILL.md.powershell`)

### 1) Prerequisites: Install Native WezTerm

- Install Windows native WezTerm (`.exe` from official site or via winget), not the Linux version inside WSL.
- Reason: `ccb` in WezTerm mode relies on `wezterm cli` to manage panes.

### 2) How to Identify Your Environment

Determine based on **how you installed/run Claude Code/Codex**:

- **WSL Environment**
  - You installed/run via WSL terminal (Ubuntu/Debian) using `bash` (e.g., `curl ... | bash`, `apt`, `pip`, `npm`)
  - Paths look like: `/home/<user>/...` and you may see `/mnt/c/...`
  - Verify: `cat /proc/version | grep -i microsoft` has output, or `echo $WSL_DISTRO_NAME` is non-empty

- **Native Windows Environment**
  - You installed/run via Windows Terminal / WezTerm / PowerShell / CMD (e.g., `winget`, PowerShell scripts)
  - Paths look like: `C:\Users\<user>\...`

### 3) WSL Users: Configure WezTerm to Auto-Enter WSL

Edit WezTerm config (`%USERPROFILE%\.wezterm.lua`):

```lua
local wezterm = require 'wezterm'
return {
  default_domain = 'WSL:Ubuntu', -- Replace with your distro name
}
```

Check distro name with `wsl -l -v` in PowerShell.

### 4) Troubleshooting: `cping` Not Working

- **Most common:** Environment mismatch (ccb in WSL but codex in native Windows, or vice versa)
- **Codex session not running:** Run `ccb codex` (or add codex to ccb.config) first
- **WezTerm CLI not found:** Ensure `wezterm` is in PATH
- **Terminal not refreshed:** Restart WezTerm after installation
- **Text sent but not submitted (no Enter) on Windows WezTerm:** Set `CCB_WEZTERM_ENTER_METHOD=key` and ensure your WezTerm supports `wezterm cli send-key`

</details>

<details>
<summary><b>🍎 macOS Installation Guide</b></summary>

### Command Not Found After Installation

If `ccb`, `cask`, `cping` commands are not found after running `./install.sh install`:

**Cause:** The install directory (`$CODEX_BIN_DIR` or default `~/.local/bin`) is not in your PATH.

**Solution:**

```bash
# 1. Check if install directory exists
ls -la "${CODEX_BIN_DIR:-$HOME/.local/bin}/"

# 2. Check if PATH includes the directory
echo $PATH | tr ':' '\n' | grep local

# 3. Check shell config (macOS defaults to zsh)
cat ~/.zshrc | grep local

# 4. If not configured, add manually
echo 'export PATH="${CODEX_BIN_DIR:-$HOME/.local/bin}:$PATH"' >> ~/.zshrc

# 5. Reload config
source ~/.zshrc
```

### WezTerm Not Detecting Commands

If WezTerm cannot find ccb commands but regular Terminal can:

- WezTerm may use a different shell config
- Add PATH to `~/.zprofile` as well:

```bash
echo 'export PATH="${CODEX_BIN_DIR:-$HOME/.local/bin}:$PATH"' >> ~/.zprofile
```

Then restart WezTerm completely (Cmd+Q, reopen).

</details>

---

## 🗣️ Usage

Once started, collaborate naturally. Claude will detect when to delegate tasks.

**Common Scenarios:**

- **Code Review:** *"Have Codex review the changes in `main.py`."*
- **Second Opinion:** *"Ask Gemini for alternative implementation approaches."*
- **Pair Programming:** *"Codex writes the backend logic, I'll handle the frontend."*
- **Architecture:** *"Let Codex design the module structure first."*
- **Info Exchange:** *"Fetch 3 rounds of Codex conversation and summarize."*

### 🎴 Fun & Creative: AI Poker Night!

> *"Let Claude, Codex and Gemini play Dou Di Zhu! You deal the cards, everyone plays open hand!"*
>
> 🃏 Claude (Landlord) vs 🎯 Codex + 💎 Gemini (Farmers)

> **Note:** Manual commands (like `cask`, `cping`) are usually invoked by Claude automatically. See Command Reference for details.

---

## 🛠️ Unified Command System

### Legacy Commands (Deprecated)
- `cask/gask/oask/dask/lask` - Independent ask commands per provider
- `cping/gping/oping/dping/lping` - Independent ping commands  
- `cpend/gpend/opend/dpend/lpend` - Independent pend commands

### Unified Commands
- **`ask <provider> <message>`** - Unified request (background by default)
  - Supports: `gemini`, `codex`, `opencode`, `droid`, `claude`
  - Defaults to background; managed Codex sessions prefer foreground to avoid cleanup
  - Override with `--foreground` / `--background` or `CCB_ASK_FOREGROUND=1` / `CCB_ASK_BACKGROUND=1`
  - Foreground uses sync send and disables completion hook unless `CCB_COMPLETION_HOOK_ENABLED` is set
  - Supports `--notify` for short synchronous notifications
  - Supports `CCB_CALLER` (default: `codex` in Codex sessions, otherwise `claude`)

- **`ping <provider>`** - Unified connectivity test
  - Checks if the specified provider's daemon is online

- **`pend <provider> [N]`** - Unified reply fetch
  - Fetches latest N replies from the provider
  - Optional N specifies number of recent messages

### Skills System
- `/ask <provider> <message>` - Request skill (background by default; foreground in managed Codex sessions)
- `/ping <provider>` - Connectivity test skill
- `/pend <provider>` - Reply fetch skill

### Cross-Platform Support
- **Linux/macOS/WSL**: Uses `tmux` as terminal backend
- **Windows WezTerm**: Uses **PowerShell** as terminal backend
- **Windows PowerShell**: Native support via `DETACHED_PROCESS` background execution

### Completion Hook
- Notifies caller upon task completion
- Supports `CCB_CALLER` targeting (`claude`/`codex`/`droid`)
- Compatible with both tmux and WezTerm backends
 - Foreground ask suppresses the hook unless `CCB_COMPLETION_HOOK_ENABLED` is set

---

## 🧩 Skills

- **/all-plan**: Collaborative multi-AI design with Superpowers brainstorming.

<details>
<summary><b>/all-plan details & usage</b></summary>

Usage:
```
/all-plan <requirement>
```

Example:
```
/all-plan Design a caching layer for the API with Redis
```

How it works:
1. **Requirement Refinement** - Socratic questioning to uncover hidden needs
2. **Parallel Independent Design** - Each AI designs independently (no groupthink)
3. **Comparative Analysis** - Merge insights, detect anti-patterns
4. **Iterative Refinement** - Cross-AI review and critique
5. **Final Output** - Actionable implementation plan

Key features:
- **Socratic Ladder**: 7 structured questions for deep requirement mining
- **Superpowers Lenses**: Systematic alternative exploration (10x scale, remove dependency, invert flow)
- **Anti-pattern Detection**: Proactive risk identification across all designs

When to use:
- Complex features requiring diverse perspectives
- Architectural decisions with multiple valid approaches
- High-stakes implementations needing thorough validation

</details>

---

## 📧 Mail System Configuration

The mail system allows you to interact with AI providers via email, enabling remote access when you're away from your terminal.

### How It Works

1. **Send an email** to your CCB service mailbox
2. **Specify the AI provider** using a prefix in the email body (e.g., `CLAUDE: your question`)
3. **CCB routes the request** to the specified AI provider via the ASK system
4. **Receive the response** via email reply

### Quick Setup

**Step 1: Run the configuration wizard**
```bash
maild setup
```

**Step 2: Choose your email provider**
- Gmail
- Outlook
- QQ Mail
- 163 Mail
- Custom IMAP/SMTP

**Step 3: Enter credentials**
- Service email address (CCB's mailbox)
- App password (not your regular password - see provider-specific instructions below)
- Target email (where to send replies)

**Step 4: Start the mail daemon**
```bash
maild start
```

### Configuration File

Configuration is stored in `~/.ccb/mail/config.json`:

```json
{
  "version": 3,
  "enabled": true,
  "service_account": {
    "provider": "gmail",
    "email": "your-ccb-service@gmail.com",
    "imap": {"host": "imap.gmail.com", "port": 993, "ssl": true},
    "smtp": {"host": "smtp.gmail.com", "port": 587, "starttls": true}
  },
  "target_email": "your-phone@example.com",
  "default_provider": "claude",
  "polling": {
    "use_idle": true,
    "idle_timeout": 300
  }
}
```

### Provider-Specific Setup

<details>
<summary><b>Gmail</b></summary>

1. Enable 2-Step Verification in your Google Account
2. Go to [App Passwords](https://myaccount.google.com/apppasswords)
3. Generate a new app password for "Mail"
4. Use this 16-character password (not your Google password)

</details>

<details>
<summary><b>Outlook / Office 365</b></summary>

1. Enable 2-Step Verification in your Microsoft Account
2. Go to [Security > App Passwords](https://account.live.com/proofs/AppPassword)
3. Generate a new app password
4. Use this password for CCB mail configuration

</details>

<details>
<summary><b>QQ Mail</b></summary>

1. Log in to QQ Mail web interface
2. Go to Settings > Account
3. Enable IMAP/SMTP service
4. Generate an authorization code (授权码)
5. Use this authorization code as the password

</details>

<details>
<summary><b>163 Mail</b></summary>

1. Log in to 163 Mail web interface
2. Go to Settings > POP3/SMTP/IMAP
3. Enable IMAP service
4. Set an authorization password (客户端授权密码)
5. Use this authorization password for CCB

</details>

### Email Format

**Basic format:**
```
Subject: Any subject (ignored)
Body:
CLAUDE: What is the weather like today?
```

**Supported provider prefixes:**
- `CLAUDE:` or `claude:` - Route to Claude
- `CODEX:` or `codex:` - Route to Codex
- `GEMINI:` or `gemini:` - Route to Gemini
- `OPENCODE:` or `opencode:` - Route to OpenCode
- `DROID:` or `droid:` - Route to Droid

If no prefix is specified, the request goes to the `default_provider` (default: `claude`).

### Mail Daemon Commands

```bash
maild start          # Start the mail daemon
maild stop           # Stop the mail daemon
maild status         # Check daemon status
maild config         # Show current configuration
maild setup          # Run configuration wizard
maild test           # Test email connectivity
```

---

<img src="assets/nvim.png" alt="Neovim integration with multi-AI code review" width="900">

> Combine with editors like **Neovim** for seamless code editing and multi-model review workflow. Edit in your favorite editor while AI assistants review and suggest improvements in real-time.

---

## 📋 Requirements

- **Python 3.10+**
- **Terminal:** [WezTerm](https://wezfurlong.org/wezterm/) (Highly Recommended) or tmux

---

## 🗑️ Uninstall

```bash
ccb uninstall
ccb reinstall

# Fallback:
./install.sh uninstall
```

---

<div align="center">

**Windows fully supported** (WSL + Native via WezTerm)

---

**Join our community**

📧 Email: bfly123@126.com
💬 WeChat: seemseam-com

<img src="assets/weixin.png" alt="WeChat Group" width="300">

</div>

---

<details>
<summary><b>Version History</b></summary>

### v5.0.6
- **Zombie Cleanup**: `ccb kill -f` cleans up orphaned tmux sessions globally
- **Mounted Skill**: Optimized with `pgrep`, extracted to `ccb-mounted` script
- **Droid Skills**: Full skill set added to `droid_skills/`

### v5.0.5
- **Droid**: Add delegation tools (`ccb_ask_*` and `cask/gask/lask/oask`) plus `ccb droid setup-delegation` for MCP install

### v5.0.4
- **OpenCode**: 修复 `-r` 恢复在多项目切换后失效的问题

### v5.0.3
- **Daemons**: 全新的稳定守护进程设计

### v5.0.1
- **Skills**: New `/all-plan` with Superpowers brainstorming + availability gating; Codex `lping/lpend` added; `gask` keeps brief summaries with `CCB_DONE`.
- **CCA Status Bar**: CCA label now reads role name from `.autoflow/roles.json` (supports `_meta.name`) and caches per path.
- **Installer**: Copy skill subdirectories (e.g., `references/`) for Claude/Codex installs.
- **CLI**: Added `ccb uninstall` / `ccb reinstall` with Claude config cleanup.
- **Routing**: Tighter project/session resolution (prefer `.ccb_config` anchor; avoid cross-project Claude session mismatches).

### v5.0.0
- **Claude Independence**: No need to start Claude first; Codex (or any agent) can be the primary CLI
- **Unified Control**: Single entry point controls Claude/OpenCode/Gemini equally
- **Simplified Launch**: Removed `ccb up`; default `ccb.config` is auto-created when missing
- **Flexible Mounting**: More flexible pane mounting and session binding
- **Daemon Autostart**: `caskd`/`laskd` auto-start in WezTerm/tmux when needed
- **Session Robustness**: PID liveness checks prevent stale sessions

### v4.1.3
- **Codex Config**: Automatically migrate deprecated `sandbox_mode = "full-auto"` to `"danger-full-access"` to fix Codex startup
- **Stability**: Fixed race conditions where fast-exiting commands could close panes before `remain-on-exit` was set
- **Tmux**: More robust pane detection (prefer stable `$TMUX_PANE` env var) and better fallback when split targets disappear

### v4.1.2
- **Performance**: Added caching for tmux status bar (git branch & ccb status) to reduce system load
- **Strict Tmux**: Explicitly require `tmux` for auto-launch; removed error-prone auto-attach logic
- **CLI**: Added `--print-version` flag for fast version checks

### v4.1.1
- **CLI Fix**: Improved flag preservation (e.g., `-a`) when relaunching `ccb` in tmux
- **UX**: Better error messages when running in non-interactive sessions
- **Install**: Force update skills to ensure latest versions are applied

### v4.1.0
- **Async Guardrail**: `cask/gask/oask` prints a post-submit guardrail reminder for Claude
- **Sync Mode**: add `--sync` to suppress guardrail prompts for Codex callers
- **Codex Skills**: update `oask/gask` skills to wait silently with `--sync`

### v4.0.9
- **Project_ID Simplification**: `ccb_project_id` uses current-directory `.ccb_config/` anchor (no ancestor traversal, no git dependency)
- **Codex Skills Stability**: Codex `oask/gask` skills default to waiting (`--timeout -1`) to avoid sending the next task too early

### v4.0.8
- **Daemon Log Binding Refresh**: `caskd` daemon now periodically refreshes `.codex-session` log paths by parsing `start_cmd` and scanning latest logs
- **Tmux Clipboard Enhancement**: Added `xsel` support and `update-environment` for better clipboard integration across GUI/remote sessions

### v4.0.7
- **Tmux Status Bar Redesign**: Dual-line status bar with modern dot indicators (●/○), git branch, CCA status, and CCB version display
- **Session Freshness**: Always scan logs for latest session instead of using cached session file
- **Simplified Auto Mode**: Removed CCA detection logic from `ccb -a`, now purely uses `--dangerously-skip-permissions`

### v4.0.6
- **Session Overrides**: `cping/gping/oping/cpend/opend` support `--session-file` / `CCB_SESSION_FILE` to bypass wrong `cwd`

### v4.0.5
- **Gemini Reliability**: Retry reading Gemini session JSON to avoid transient partial-write failures
- **Claude Code Reliability**: `gpend` supports `--session-file` / `CCB_SESSION_FILE` to bypass wrong `cwd`

### v4.0.4
- **Fix**: Auto-repair duplicate `[projects.\"...\"]` entries in `~/.codex/config.toml` before starting Codex

### v4.0.3
- **Project Cleanliness**: Store session files under `.ccb_config/` (fallback to legacy root dotfiles)
- **Claude Code Reliability**: `cask/gask/oask` support `--session-file` / `CCB_SESSION_FILE` to bypass wrong `cwd`
- **Codex Config Safety**: Write auto-approval settings into a CCB-marked block to avoid config conflicts

### v4.0.2
- **CCA Detection**: Improved install directory inference for various layouts
- **Clipboard Paste**: Cross-platform support (xclip/wl-paste/pbpaste) in tmux config
- **Install UX**: Auto-reload tmux config after installation
- **Stability**: Default TMUX_ENTER_DELAY set to 0.5s for better reliability

### v4.0.1
- **Tokyo Night Theme**: Switch tmux status bar and pane borders to Tokyo Night color palette

### v4.0
- **Full Refactor**: Rebuilt from the ground up with a cleaner architecture
- **Perfect tmux Support**: First-class splits, pane labels, borders and statusline
- **Works in Any Terminal**: Recommended to run everything in tmux (except native Windows)

### v3.0.0
- **Smart Daemons**: `caskd`/`gaskd`/`oaskd` with 60s idle timeout & parallel queue support
- **Cross-AI Collaboration**: Support multiple agents (Claude/Codex) calling one agent (OpenCode) simultaneously
- **Interruption Detection**: Gemini now supports intelligent interruption handling
- **Chained Execution**: Codex can call `oask` to drive OpenCode
- **Stability**: Robust queue management and lock files

### v2.3.9
- Fix oask session tracking bug - follow new session when OpenCode creates one

### v2.3.8
- Simplify CCA detection: check for `.autoflow` folder in current directory
- Plan mode enabled for CCA projects regardless of `-a` flag

### v2.3.7
- Per-directory lock: different working directories can run cask/gask/oask independently

### v2.3.6
- Add non-blocking lock for cask/gask/oask to prevent concurrent requests
- Unify oask with cask/gask logic (use _wait_for_complete_reply)

### v2.3.5
- Fix plan mode conflict with auto mode (--dangerously-skip-permissions)
- Fix oask returning stale reply when OpenCode still processing

### v2.3.4
- Auto-enable plan mode when CCA (Claude Code Autoflow) is installed

### v2.3.3
- Simplify cping.md to match oping/gping style (~65% token reduction)

### v2.3.2
- Optimize skill files: extract common patterns to docs/async-ask-pattern.md (~60% token reduction)

### v2.3.1
- Fix race condition in gask/cask: pre-check for existing messages before wait loop

</details>
