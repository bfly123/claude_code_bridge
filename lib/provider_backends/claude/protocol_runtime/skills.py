from __future__ import annotations

from pathlib import Path

from runtime_env import env_bool

_SKILL_CACHE: str | None = None


def load_claude_skills() -> str:
    global _SKILL_CACHE
    if _SKILL_CACHE is not None:
        return _SKILL_CACHE
    if not env_bool('CCB_CLAUDE_SKILLS', True):
        _SKILL_CACHE = ''
        return _SKILL_CACHE
    skills_dir = Path(__file__).resolve().parents[2] / 'claude_skills'
    if not skills_dir.is_dir():
        _SKILL_CACHE = ''
        return _SKILL_CACHE
    parts: list[str] = []
    for name in ('ask.md',):
        path = skills_dir / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding='utf-8').strip()
        except Exception:
            continue
        if text:
            parts.append(text)
    _SKILL_CACHE = '\n\n'.join(parts).strip()
    return _SKILL_CACHE


__all__ = ['load_claude_skills']
