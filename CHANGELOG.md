# Changelog

All notable changes to CCB Multi are documented here.
This project uses its own version line, independent from upstream CCB.

## Unreleased

## v1.0.0 (2026-02-18)

Initial release as independent fork. Based on upstream CCB v5.2.6.

### 🚀 Multi-Instance Support

- **ccb-multi**: Launch multiple CCB instances in the same project with independent contexts
- **ccb-multi-status**: Real-time status monitoring for all instances
- **ccb-multi-history**: View instance execution history
- **ccb-multi-clean**: Clean up stale instance directories
- **Collision-Free Naming**: Instance dirs use `inst-<hash>-N` format (8-char SHA-256 of project root)

### 🔧 LLM Communication Fixes (upstream-unmerged)

- **Gemini CLI 0.29.0 Deadlock**: Dual-format session scanning (basename + SHA-256 hash) with auto-adoption
- **Hash Persistence**: `_all_known_hashes` set survives hash format transitions
- **Daemon work_dir Decoupling**: `--work-dir` parameter and `CCB_WORK_DIR` env for `bin/askd`
- **State Validation**: `bin/ask` validates daemon's `work_dir` with fallback to `cwd`
- **Cross-Hash Guard**: Instance mode blocks cross-hash session override to prevent contamination

### 🔧 Inherited from Upstream CCB v5.2.5

- Async Guardrail hardening (global turn-stop rule)
- Marker consistency for `[CCB_ASYNC_SUBMITTED]`
- Project-local history (`.ccb/history/`)
- Session switch capture and context transfer
- Unified command system (`ask`, `ccb-ping`, `pend`)
- Windows WezTerm + PowerShell support
- Email-to-AI gateway (mail system)

---

For upstream CCB changelog prior to this fork, see [CHANGELOG_4.0.md](CHANGELOG_4.0.md) or the [upstream repo](https://github.com/bfly123/claude_code_bridge).
