"""Agent name aliases for CCB.

Resolves short aliases (a, b, c, ...) to provider names.

Configuration layers (higher overrides lower):
1. Hardcoded defaults (DEFAULT_ALIASES)
2. ~/.ccb/aliases.json (global)
3. .ccb/aliases.json (project-level, relative to work_dir)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Optional

DEFAULT_ALIASES: Dict[str, str] = {
    "a": "codex",
    "b": "gemini",
    "c": "claude",
    "d": "opencode",
    "e": "droid",
    "f": "copilot",
    "g": "codebuddy",
    "h": "qwen",
}


def _load_json(path: Path) -> Dict[str, str]:
    """Load aliases from a JSON file, returning {} on any error."""
    try:
        if not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        # Only keep str->str entries
        return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError, ValueError):
        print(f"[WARN] Failed to parse alias config: {path}", file=sys.stderr)
        return {}


def load_aliases(work_dir: Optional[Path] = None) -> Dict[str, str]:
    """Merge alias configs: defaults < ~/.ccb/aliases.json < .ccb/aliases.json."""
    merged = dict(DEFAULT_ALIASES)

    global_path = Path.home() / ".ccb" / "aliases.json"
    merged.update(_load_json(global_path))

    if work_dir is not None:
        project_path = work_dir / ".ccb" / "aliases.json"
        merged.update(_load_json(project_path))

    return merged


def resolve_alias(name: str, aliases: Dict[str, str]) -> str:
    """Resolve an alias to a provider name. Non-aliases pass through unchanged."""
    key = (name or "").strip().lower()
    return aliases.get(key, key)
