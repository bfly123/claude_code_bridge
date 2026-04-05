---
name: continue
description: Attach the newest context-transfer Markdown from the current project's ./.ccb/history/ into Claude using @file. Use when the user types /continue or asks to resume with the latest transfer file in this project.
---

# Continue (Attach Latest History)

## Overview

Find the newest Markdown in `./.ccb/history/` (or legacy `./.ccb_config/history/`) and reply with an `@file` reference so Claude loads it.

## Workflow

1. Locate the newest `.md` under the current project's history folder.
2. If none exists, report that no history file was found.
3. Reply with a single line `@<path>` and nothing else.

## Execution (MANDATORY)

```bash
latest="$(ls -t "$PWD"/.ccb/history/*.md 2>/dev/null | head -n 1)"
if [[ -z "$latest" ]]; then
  latest="$(ls -t "$PWD"/.ccb_config/history/*.md 2>/dev/null | head -n 1)"
fi
if [[ -z "$latest" ]]; then
  echo "No history file found in ./.ccb/history."
  exit 0
fi
printf '@%s\n' "$latest"
```

## Output Rules

- When a history file exists: output only `@<path>` on a single line.
- When none exists: output the error message and stop.

## Examples

- `/continue` -> `@/home/bfly/workspace/hippocampus/.ccb/history/claude-20260208-225221-9f236442.md`
