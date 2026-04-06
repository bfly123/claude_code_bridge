from __future__ import annotations

import json
from pathlib import Path
import re

RETIRED_ASK_SHORTCUT_COMMANDS = (
    'bask',
    'cask',
    'dask',
    'gask',
    'hask',
    'lask',
    'oask',
    'qask',
)
RETIRED_PEND_COMMANDS = (
    'bpend',
    'cpend',
    'dpend',
    'gpend',
    'hpend',
    'lpend',
    'opend',
    'qpend',
)
RETIRED_PING_COMMANDS = (
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
            *(f'{command}.md' for command in RETIRED_ASK_SHORTCUT_COMMANDS),
            *(f'{command}.md' for command in RETIRED_PEND_COMMANDS),
            *(f'{command}.md' for command in RETIRED_PING_COMMANDS),
        }
    )
)
RETIRED_PERMISSION_ALLOW_LITERALS = (
    'Bash(ccb provider ping *)',
    'Bash(ccb provider pend *)',
    'Bash(ccb-ping *)',
    'Bash(pend *)',
)
RETIRED_SECTION_PATTERNS = (
    r"## Codex Collaboration Rules.*?(?=\n## (?!Gemini)|\Z)",
    r"## Codex 协作规则.*?(?=\n## |\Z)",
    r"## Gemini Collaboration Rules.*?(?=\n## |\Z)",
    r"## Gemini 协作规则.*?(?=\n## |\Z)",
    r"## OpenCode Collaboration Rules.*?(?=\n## |\Z)",
    r"## OpenCode 协作规则.*?(?=\n## |\Z)",
)


def _retired_permission_allow_entries() -> set[str]:
    entries = {f'Bash({command}:*)' for command in RETIRED_ASK_SHORTCUT_COMMANDS}
    entries.update(RETIRED_PERMISSION_ALLOW_LITERALS)
    entries.update(f'Bash({command})' for command in RETIRED_PEND_COMMANDS)
    entries.update(f'Bash({command})' for command in RETIRED_PING_COMMANDS)
    return entries


def _command_dirs(claude_dir: Path) -> tuple[Path, ...]:
    home = Path.home()
    return (
        claude_dir / "commands",
        home / ".config" / "claude" / "commands",
        home / ".local" / "share" / "claude" / "commands",
    )


def _remove_retired_command_docs(command_dirs: tuple[Path, ...]) -> None:
    for cmd_dir in command_dirs:
        if not cmd_dir.is_dir():
            continue
        for name in CLAUDE_COMMAND_DOCS:
            try:
                (cmd_dir / name).unlink(missing_ok=True)
            except Exception:
                pass


def _strip_retired_sections(content: str) -> str:
    stripped = re.sub(
        r"\n?<!-- CCB_CONFIG_START -->.*?<!-- CCB_CONFIG_END -->\n?",
        "\n",
        content,
        flags=re.DOTALL,
    )
    for pattern in RETIRED_SECTION_PATTERNS:
        stripped = re.sub(pattern, "", stripped, flags=re.DOTALL)
    return stripped.strip()


def _cleanup_claude_md(claude_md: Path) -> None:
    if not claude_md.is_file():
        return
    try:
        content = claude_md.read_text(encoding="utf-8", errors="replace")
    except Exception:
        content = ""
    if not content:
        return
    cleaned = _strip_retired_sections(content)
    if cleaned != content.strip():
        claude_md.write_text((cleaned + "\n") if cleaned else "", encoding="utf-8")


def _load_json_object(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_json_object(path: Path, data: dict) -> None:
    rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_text(rendered, encoding="utf-8")


def _cleanup_settings_permissions(settings_json: Path) -> None:
    if not settings_json.is_file():
        return
    data = _load_json_object(settings_json)
    perms = data.get("permissions")
    allow = perms.get("allow") if isinstance(perms, dict) else None
    if not isinstance(allow, list):
        return
    to_remove = _retired_permission_allow_entries()
    new_allow = [entry for entry in allow if entry not in to_remove]
    if new_allow == allow:
        return
    perms["allow"] = new_allow
    _save_json_object(settings_json, data)


def cleanup_claude_files() -> None:
    claude_dir = Path.home() / ".claude"
    claude_md = claude_dir / "CLAUDE.md"
    settings_json = claude_dir / "settings.json"
    _remove_retired_command_docs(_command_dirs(claude_dir))
    _cleanup_claude_md(claude_md)
    _cleanup_settings_permissions(settings_json)


__all__ = ["CLAUDE_COMMAND_DOCS", "cleanup_claude_files"]
