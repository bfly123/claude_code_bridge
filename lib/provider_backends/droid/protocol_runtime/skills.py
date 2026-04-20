from __future__ import annotations

from pathlib import Path

from runtime_env import env_bool

_SKILL_CACHE: str | None = None


def load_droid_skills() -> str:
    global _SKILL_CACHE
    if _SKILL_CACHE is not None:
        return _SKILL_CACHE
    if not env_bool("CCB_DROID_SKILLS", True):
        _SKILL_CACHE = ""
        return _SKILL_CACHE

    skills_dir = Path(__file__).resolve().parents[2] / "droid_skills"
    if not skills_dir.is_dir():
        _SKILL_CACHE = ""
        return _SKILL_CACHE

    parts: list[str] = []
    for name in ("codex.md", "gemini.md", "claude.md", "opencode.md"):
        text = _read_skill_text(skills_dir / name)
        if text:
            parts.append(text)
    _SKILL_CACHE = "\n\n".join(parts).strip()
    return _SKILL_CACHE


def _read_skill_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


__all__ = ["load_droid_skills"]
