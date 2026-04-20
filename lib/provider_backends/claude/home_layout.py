from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class ClaudeHomeLayout:
    home_root: Path
    claude_dir: Path
    projects_root: Path
    session_env_root: Path
    trust_path: Path
    settings_path: Path


def claude_layout_for_home(home_root: Path) -> ClaudeHomeLayout:
    root = Path(home_root).expanduser()
    claude_dir = root / '.claude'
    return ClaudeHomeLayout(
        home_root=root,
        claude_dir=claude_dir,
        projects_root=claude_dir / 'projects',
        session_env_root=claude_dir / 'session-env',
        trust_path=root / '.claude.json',
        settings_path=claude_dir / 'settings.json',
    )


def current_claude_home_root() -> Path:
    projects_root = _env_projects_root()
    if projects_root is not None:
        home_root = _home_root_from_projects_root(projects_root)
        if home_root is not None:
            return home_root
    return Path.home().expanduser()


def current_claude_projects_root() -> Path:
    env_root = _env_projects_root()
    if env_root is not None:
        return env_root
    return claude_layout_for_home(Path.home()).projects_root


def current_claude_session_env_root() -> Path:
    return claude_layout_for_home(current_claude_home_root()).session_env_root


def claude_layout_from_session_data(data: dict[str, object] | None) -> ClaudeHomeLayout | None:
    if not isinstance(data, dict):
        return None
    home_root = _path_or_none(data.get('claude_home'))
    if home_root is not None:
        return claude_layout_for_home(home_root)

    projects_root = _path_or_none(data.get('claude_projects_root'))
    if projects_root is not None:
        home_root = _home_root_from_projects_root(projects_root)
        if home_root is not None:
            return claude_layout_for_home(home_root)

    session_env_root = _path_or_none(data.get('claude_session_env_root'))
    if session_env_root is not None:
        home_root = _home_root_from_session_env_root(session_env_root)
        if home_root is not None:
            return claude_layout_for_home(home_root)

    session_path = _path_or_none(data.get('claude_session_path'))
    if session_path is not None:
        home_root = _home_root_from_session_path(session_path)
        if home_root is not None:
            return claude_layout_for_home(home_root)
    return None


def _env_projects_root() -> Path | None:
    raw = str(
        os.environ.get('CLAUDE_PROJECTS_ROOT')
        or os.environ.get('CLAUDE_PROJECT_ROOT')
        or ''
    ).strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser()
    except Exception:
        return None


def _home_root_from_projects_root(projects_root: Path) -> Path | None:
    root = Path(projects_root).expanduser()
    if root.name != 'projects':
        return None
    parent = root.parent
    if not parent.name:
        return None
    if parent.name == '.claude':
        return parent.parent
    return None


def _home_root_from_session_env_root(session_env_root: Path) -> Path | None:
    root = Path(session_env_root).expanduser()
    if root.name != 'session-env':
        return None
    parent = root.parent
    if not parent.name:
        return None
    if parent.name == '.claude':
        return parent.parent
    return None


def _home_root_from_session_path(session_path: Path) -> Path | None:
    candidate = Path(session_path).expanduser()
    for parent in candidate.parents:
        if parent.name == '.claude':
            return parent.parent
    return None


def _path_or_none(value: object) -> Path | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser()
    except Exception:
        return None


__all__ = [
    'ClaudeHomeLayout',
    'claude_layout_for_home',
    'claude_layout_from_session_data',
    'current_claude_home_root',
    'current_claude_projects_root',
    'current_claude_session_env_root',
]
