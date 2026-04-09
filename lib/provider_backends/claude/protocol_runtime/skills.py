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
    _SKILL_CACHE = load_claude_skills_from_dir(default_claude_skills_dir())
    return _SKILL_CACHE


def load_claude_skills_from_dir(skills_dir: Path) -> str:
    if not skills_dir.is_dir():
        return ''
    parts: list[str] = []
    text = _first_existing_skill_text(_skill_paths(skills_dir))
    if text:
        parts.append(text)
    return '\n\n'.join(parts).strip()


def default_claude_skills_dir() -> Path:
    return Path(__file__).resolve().parents[4] / 'claude_skills'


def _skill_paths(skills_dir: Path) -> tuple[Path, ...]:
    return (
        skills_dir / 'ask' / 'RUNTIME.md',
        skills_dir / 'ask' / 'SKILL.md',
        skills_dir / 'ask.md',
    )


def _first_existing_skill_text(paths: tuple[Path, ...]) -> str:
    for path in paths:
        text = _read_skill_text(path)
        if text:
            return text
    return ''


def _read_skill_text(path: Path) -> str:
    if not path.is_file():
        return ''
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        return ''
    return _strip_front_matter(text).strip()


def _strip_front_matter(text: str) -> str:
    stripped = str(text or '')
    if not stripped.startswith('---\n'):
        return stripped
    end = stripped.find('\n---\n', 4)
    if end == -1:
        return stripped
    return stripped[end + 5 :]


__all__ = ['default_claude_skills_dir', 'load_claude_skills', 'load_claude_skills_from_dir']
