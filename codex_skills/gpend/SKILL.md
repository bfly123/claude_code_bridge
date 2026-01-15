---
name: gpend
description: "Fetch the latest reply from Gemini (shorthand: g/gm) via the `gpend` CLI. Use only when the user explicitly asks to view the Gemini/gm reply/response (e.g. \"看下 g 回复/输出\"); do not run proactively after `gask` unless requested."
---

# gpend (Read Gemini Reply)

## Quick Start

- `gpend` / `gpend N` (optional override: `gpend --session-file /path/to/.gemini-session`)

## Workflow (Mandatory)

1. Run `gpend` (or `gpend N` if the user explicitly asks for N conversations).
2. Return stdout to the user verbatim.
3. If `gpend` exits `2`, report “no reply available” (do not invent output).

## Notes

- Prefer `gping` when the user’s intent is “check Gemini is up”.
