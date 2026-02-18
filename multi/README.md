# CCB Multi-Instance Manager

Multi-instance support for Claude Code Bridge with true concurrent execution.

## Features

- **🔀 Multi-Instance Isolation**: Run multiple CCB instances in the same project with independent contexts
- **⚡ Concurrent LLM Execution**: Multiple AI providers (Claude, Codex, Gemini) work in parallel, not sequentially
- **📊 Real-time Status Monitoring**: Check all instance status with `ccb-multi-status`
- **🧹 Instance Management**: Create, list, and clean instances easily
- **🔒 Collision-Free Naming**: Instance dirs use `inst-<hash>-N` format (8-char SHA-256 of project root) to prevent cross-project collisions in Gemini CLI 0.29.0's basename-based session storage

## Quick Start

```bash
# Start instance 1 with Gemini
ccb-multi 1 gemini

# Start instance 2 with Codex (in another terminal)
ccb-multi 2 codex

# Start instance 3 with Claude (in another terminal)
ccb-multi 3 claude

# Check status
ccb-multi-status

# View history
ccb-multi-history

# Clean up
ccb-multi-clean
```

## Concurrent Execution

Within each instance, you can send concurrent requests to multiple LLMs:

```bash
# In your CCB session, send async requests
CCB_CALLER=claude ask gemini "task 1" &
CCB_CALLER=claude ask codex "task 2" &
CCB_CALLER=claude ask opencode "task 3" &
wait

# Check results
pend gemini
pend codex
pend opencode
```

## Architecture

- **Single Daemon**: One daemon per project manages all instances
- **Session Isolation**: Each instance has independent session context
- **Concurrent Workers**: Different sessions execute in parallel automatically
- **Shared Resources**: Worker pool and file watchers are shared efficiently

## Instance Directory Format

Instances are created under `.ccb-instances/` in the project root:

```
.ccb-instances/
  inst-a1b2c3d4-1/    # New format: inst-<projectHash>-<id>
  inst-a1b2c3d4-2/
  instance-3/          # Old format: still recognized for backward compat
```

The `<projectHash>` is an 8-character SHA-256 hash of the project root path, ensuring globally unique directory basenames across different projects.

Environment variables set per instance:
- `CCB_INSTANCE_ID` - Instance number (1, 2, 3, ...)
- `CCB_PROJECT_ROOT` - Original project root path

## Commands

- `ccb-multi <instance-id> [providers...]` - Start an instance
- `ccb-multi-status` - Show all running instances
- `ccb-multi-history` - View instance history
- `ccb-multi-clean` - Clean up stale instances
