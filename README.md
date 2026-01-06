<div align="center">

# Claude Code Bridge (ccb) v2.3.6

**Silky Smooth Claude & Codex & Gemini Collaboration via Split-Pane Terminal**

**Build a real AI expert team. Give Claude Code / Codex / Gemini / OpenCode partners that never forget.**

<p>
  <img src="https://img.shields.io/badge/交互皆可见-096DD9?style=for-the-badge" alt="交互皆可见">
  <img src="https://img.shields.io/badge/模型皆可控-CF1322?style=for-the-badge" alt="模型皆可控">
</p>
<p>
  <img src="https://img.shields.io/badge/Every_Interaction_Visible-096DD9?style=for-the-badge" alt="Every Interaction Visible">
  <img src="https://img.shields.io/badge/Every_Model_Controllable-CF1322?style=for-the-badge" alt="Every Model Controllable">
</p>

[![Version](https://img.shields.io/badge/version-2.3.6-orange.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)]()

**English** | [中文](README_zh.md)

<img src="assets/demo.webp" alt="Split-pane collaboration demo" width="900">

</div>

---

**Introduction:** Multi-model collaboration effectively avoids model bias, cognitive blind spots, and context limitations. However, MCP, Skills and other direct API approaches have many limitations. This project offers a new solution.

## ⚡ Why ccb?

| Feature | Benefit |
| :--- | :--- |
| **🖥️ Visual & Controllable** | Multiple AI models in split-pane CLI. See everything, control everything. |
| **🧠 Persistent Context** | Each AI maintains its own memory. Close and resume anytime (`-r` flag). |
| **📉 Token Savings** | Sends lightweight prompts instead of full file history. |
| **🪟 Native Workflow** | Integrates directly into **WezTerm** (recommended) or tmux. No complex servers required. |

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

</details>

### Run
```bash
ccb up codex            # Start Codex
ccb up gemini           # Start Gemini
ccb up opencode         # Start OpenCode
ccb up codex gemini     # Start both
ccb up codex gemini opencode  # Start all three
ccb-layout              # Start 2x2 layout (Codex+Gemini+OpenCode)
```

### Flags
| Flag | Description | Example |
| :--- | :--- | :--- |
| `-r` | Resume previous session context | `ccb up codex -r` |
| `-a` | Auto-mode, skip permission prompts | `ccb up codex -a` |
| `-h` | Show help information | `ccb -h` |
| `-v` | Show version and check for updates | `ccb -v` |

### Update
```bash
ccb update              # Update ccb to the latest version
```

---

## 🪟 Windows Installation Guide (WSL vs Native)

> **Key Point:** `ccb/cask-w/cping` must run in the **same environment** as `codex/gemini`. The most common issue is environment mismatch causing `cping` to fail.

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
- **Codex session not running:** Run `ccb up codex` first
- **WezTerm CLI not found:** Ensure `wezterm` is in PATH
- **Terminal not refreshed:** Restart WezTerm after installation

---

## 🍎 macOS Installation Guide

### Command Not Found After Installation

If `ccb`, `cask`, `cping` commands are not found after running `./install.sh install`:

**Cause:** The install directory (`~/.local/bin`) is not in your PATH.

**Solution:**

```bash
# 1. Check if install directory exists
ls -la ~/.local/bin/

# 2. Check if PATH includes the directory
echo $PATH | tr ':' '\n' | grep local

# 3. Check shell config (macOS defaults to zsh)
cat ~/.zshrc | grep local

# 4. If not configured, add manually
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc

# 5. Reload config
source ~/.zshrc
```

### WezTerm Not Detecting Commands

If WezTerm cannot find ccb commands but regular Terminal can:

- WezTerm may use a different shell config
- Add PATH to `~/.zprofile` as well:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile
```

Then restart WezTerm completely (Cmd+Q, reopen).

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

> *"Let Claude, Codex and Gemini play Dou Di Zhu (斗地主)! You deal the cards, everyone plays open hand!"*
>
> 🃏 Claude (Landlord) vs 🎯 Codex + 💎 Gemini (Farmers)

> **Note:** Manual commands (like `cask`, `cping`) are usually invoked by Claude automatically. See Command Reference for details.

---

## 📝 Command Reference

### Codex Commands

| Command | Description |
| :--- | :--- |
| `/cask <msg>` | Background mode: Submit task to Codex, free to continue other tasks (recommended) |
| `/cask-w <msg>` | Foreground mode: Submit task and wait for response, faster but blocking |
| `cpend [N]` | Fetch Codex conversation history, N controls rounds (default 1) |
| `cping` | Test Codex connectivity |

### Gemini Commands

| Command | Description |
| :--- | :--- |
| `/gask <msg>` | Background mode: Submit task to Gemini |
| `/gask-w <msg>` | Foreground mode: Submit task and wait for response |
| `gpend [N]` | Fetch Gemini conversation history |
| `gping` | Test Gemini connectivity |

---

## 🖥️ Editor Integration: Neovim + Multi-AI Review

<img src="assets/nvim.png" alt="Neovim integration with multi-AI code review" width="900">

> Combine with editors like **Neovim** for seamless code editing and multi-model review workflow. Edit in your favorite editor while AI assistants review and suggest improvements in real-time.

---

## 📋 Requirements

- **Python 3.10+**
- **Terminal:** [WezTerm](https://wezfurlong.org/wezterm/) (Highly Recommended) or tmux

---

## 🗑️ Uninstall

```bash
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
