from __future__ import annotations

import json
from pathlib import Path
import re

LEGACY_ASK_SHORTCUT_COMMANDS = (
    'bask',
    'cask',
    'dask',
    'gask',
    'hask',
    'lask',
    'oask',
    'qask',
)
LEGACY_PEND_COMMANDS = (
    'bpend',
    'cpend',
    'dpend',
    'gpend',
    'hpend',
    'lpend',
    'opend',
    'qpend',
)
LEGACY_PING_COMMANDS = (
    'bping',
    'cping',
    'dping',
    'gping',
    'hping',
    'lping',
    'oping',
    'qping',
)

CLAUDE_COMMAND_DOCS = tuple(
    sorted(
        {
            *(f'{command}.md' for command in LEGACY_ASK_SHORTCUT_COMMANDS),
            *(f'{command}.md' for command in LEGACY_PEND_COMMANDS),
            *(f'{command}.md' for command in LEGACY_PING_COMMANDS),
        }
    )
)


def _obsolete_permission_allow_entries() -> set[str]:
    entries = {f'Bash({command}:*)' for command in LEGACY_ASK_SHORTCUT_COMMANDS}
    entries.update({'Bash(ccb provider ping *)', 'Bash(ccb provider pend *)', 'Bash(ccb-ping *)', 'Bash(pend *)'})
    entries.update(f'Bash({command})' for command in LEGACY_PEND_COMMANDS)
    entries.update(f'Bash({command})' for command in LEGACY_PING_COMMANDS)
    return entries


def cleanup_claude_files() -> None:
    claude_dir = Path.home() / ".claude"
    claude_md = claude_dir / "CLAUDE.md"
    settings_json = claude_dir / "settings.json"
    command_dirs = [
        claude_dir / "commands",
        Path.home() / ".config" / "claude" / "commands",
        Path.home() / ".local" / "share" / "claude" / "commands",
    ]

    for cmd_dir in command_dirs:
        if not cmd_dir.is_dir():
            continue
        for name in CLAUDE_COMMAND_DOCS:
            try:
                (cmd_dir / name).unlink(missing_ok=True)
            except Exception:
                pass

    if claude_md.is_file():
        try:
            content = claude_md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            content = ""
        if content:
            before = content
            content = re.sub(
                r"\n?<!-- CCB_CONFIG_START -->.*?<!-- CCB_CONFIG_END -->\n?",
                "\n",
                content,
                flags=re.DOTALL,
            )
            obsolete_section_patterns = [
                r"## Codex Collaboration Rules.*?(?=\n## (?!Gemini)|\Z)",
                r"## Codex 协作规则.*?(?=\n## |\Z)",
                r"## Gemini Collaboration Rules.*?(?=\n## |\Z)",
                r"## Gemini 协作规则.*?(?=\n## |\Z)",
                r"## OpenCode Collaboration Rules.*?(?=\n## |\Z)",
                r"## OpenCode 协作规则.*?(?=\n## |\Z)",
            ]
            for pattern in obsolete_section_patterns:
                content = re.sub(pattern, "", content, flags=re.DOTALL)
            content = content.strip()
            if content != before.strip():
                claude_md.write_text((content + "\n") if content else "", encoding="utf-8")

    if settings_json.is_file():
        try:
            data = json.loads(settings_json.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            data = {}
        if isinstance(data, dict):
            perms = data.get("permissions")
            allow = perms.get("allow") if isinstance(perms, dict) else None
            if isinstance(allow, list):
                to_remove = _obsolete_permission_allow_entries()
                new_allow = [entry for entry in allow if entry not in to_remove]
                if new_allow != allow:
                    perms["allow"] = new_allow
                    settings_json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
