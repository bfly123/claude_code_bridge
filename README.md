<div align="center">

# CCB Multi

**Claude Code Bridge — Multi-Instance Edition**

Run multiple CCB instances in parallel, with LLM communication fixes included.

[![Version](https://img.shields.io/badge/version-1.0.0-orange.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)]()

![Showcase](assets/show.png)

<details>
<summary><b>Demo animations</b></summary>

<img src="assets/readme_previews/video2.gif" alt="Any-terminal collaboration demo" width="900">

<img src="assets/readme_previews/video1.gif" alt="VS Code integration demo" width="900">

</details>

</div>

---

## What is CCB Multi?

An enhanced fork of [Claude Code Bridge (CCB)](https://github.com/bfly123/claude_code_bridge) that adds **multi-instance concurrent execution** and includes several upstream-unmerged LLM communication fixes. If you need to run multiple CCB sessions in the same project simultaneously, this is for you.

---

## Differences from Upstream CCB

| Feature | Upstream CCB | CCB Multi |
| :--- | :---: | :---: |
| Multi-instance concurrent execution | ❌ | ✅ |
| Gemini CLI 0.29.0 compatibility | ❌ | ✅ |
| Daemon `work_dir` decoupling | ❌ | ✅ |
| Dead-thread detection | ❌ | ✅ |
| Instance dir collision prevention | ❌ | ✅ |

---

## What's Fixed

### Gemini CLI 0.29.0 Deadlock
Gemini CLI 0.29.0 changed session storage from SHA-256 hash to directory basename (`~/.gemini/tmp/<basename>/`). CCB Multi scans both formats and auto-adopts the active one, preventing session hangs.

### Daemon work_dir Decoupling
`bin/askd` now accepts `--work-dir` (or `CCB_WORK_DIR` env) to decouple the daemon's project root from the launch directory. `bin/ask` validates the daemon's `work_dir` and falls back to `cwd` with a warning if missing.

### Worker Pool Robustness
- `GeminiLogReader` maintains `_all_known_hashes` set that survives hash format transitions
- Instance mode blocks cross-hash session override to prevent contamination between projects

### Instance Directory Basename Collision
Changed from `instance-N` to `inst-<hash>-N` format (8-char SHA-256 of project root) to prevent cross-project collisions in Gemini CLI's basename-based storage. Old `instance-N` directories are still recognized for backward compatibility.

---

## Multi-Instance Usage

### Quick Start

```bash
# Start instance 1 with Gemini
ccb-multi 1 gemini

# Start instance 2 with Codex (in another terminal)
ccb-multi 2 codex

# Start instance 3 with Claude (in another terminal)
ccb-multi 3 claude

# Check all instance status
ccb-multi-status

# View history
ccb-multi-history

# Clean up stale instances
ccb-multi-clean
```

### Instance Directory Format

Instances are created under `.ccb-instances/` in the project root:

```
.ccb-instances/
  inst-a1b2c3d4-1/    # inst-<projectHash>-<id>
  inst-a1b2c3d4-2/
  instance-3/          # Old format: still recognized
```

The `<projectHash>` is an 8-char SHA-256 of the project root path, ensuring globally unique basenames across projects.

### Environment Variables

| Variable | Description |
| :--- | :--- |
| `CCB_INSTANCE_ID` | Instance number (1, 2, 3, ...) |
| `CCB_PROJECT_ROOT` | Original project root path |
| `CCB_WORK_DIR` | Override daemon's working directory |

### Concurrent LLM Requests Within an Instance

```bash
# Send async requests to multiple LLMs
CCB_CALLER=claude ask gemini "task 1" &
CCB_CALLER=claude ask codex "task 2" &
CCB_CALLER=claude ask opencode "task 3" &
wait

# Check results
pend gemini
pend codex
pend opencode
```

---

## Installation

### Option 1: Full Install (clone this repo)

```bash
git clone https://github.com/daniellee2015/claude_code_bridge_multi.git
cd claude_code_bridge_multi
./install.sh install
```

This installs the full CCB + multi-instance tooling.

### Option 2: npm Package Only (with existing upstream CCB)

If you already have upstream CCB installed and only want the multi-instance CLI:

```bash
npm install -g ccb-multi
```

This installs `ccb-multi`, `ccb-multi-status`, `ccb-multi-history`, and `ccb-multi-clean` globally.
Source: [github.com/daniellee2015/ccb-multi](https://github.com/daniellee2015/ccb-multi)

### Update & Uninstall

```bash
ccb update              # Update to latest version
ccb uninstall           # Uninstall
ccb reinstall           # Clean reinstall
```

---

## Base CCB Documentation

For core CCB usage, command reference, skills system, mail service, and platform-specific guides, see the [upstream CCB README](https://github.com/bfly123/claude_code_bridge#readme).

Key topics covered there:
- `ccb` launch flags (`-r`, `-a`, `-h`, `-v`)
- `ccb.config` format
- Unified command system (`ask`, `ccb-ping`, `pend`)
- Skills (`/all-plan`, `/ask`, `/cping`, `/pend`)
- Mail system configuration
- Windows / WSL / macOS installation guides

---

## Version

**1.0.0** — Independent version line, forked from upstream CCB v5.2.6.

See [CHANGELOG.md](CHANGELOG.md) for details.

---

<div align="center">

**[Upstream CCB](https://github.com/bfly123/claude_code_bridge)** · **[Issues](https://github.com/daniellee2015/claude_code_bridge_multi/issues)**

</div>
