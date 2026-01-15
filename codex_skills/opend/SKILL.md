---
name: opend
description: "Fetch the latest reply from OpenCode (shorthand: oc) storage via the `opend` CLI. Use only when the user explicitly asks to view the OpenCode/oc reply/response (e.g. \"看下 oc 回复/输出\"); do not run proactively after `oask` unless requested."
---

# Opend

## Quick Start

- `opend` (optional override: `opend --session-file /path/to/.opencode-session`)

## Workflow (Mandatory)

1. Run `opend` and return stdout to the user verbatim.
2. If `opend` exits `2`, report “no reply available” (do not invent output).

## Notes

- `opend` currently does not take a numeric argument (unlike `cpend N`).
- If the user’s intent is to “check OpenCode is up”, use `oping` instead.
