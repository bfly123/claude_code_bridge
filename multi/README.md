# CCB Multi-Instance Manager

Multi-instance support for Claude Code Bridge with true concurrent execution.

## Features

- **🔀 Multi-Instance Isolation**: Run multiple CCB instances in the same project with independent contexts
- **⚡ Concurrent LLM Execution**: Multiple AI providers (Claude, Codex, Gemini) work in parallel, not sequentially
- **📊 Real-time Status Monitoring**: Check all instance status with `ccb-multi-status`
- **🧹 Instance Management**: Create, list, and clean instances easily

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

## Commands

- `ccb-multi <instance-id> [providers...]` - Start an instance
- `ccb-multi-status` - Show all running instances
- `ccb-multi-history` - View instance history
- `ccb-multi-clean` - Clean up stale instances
