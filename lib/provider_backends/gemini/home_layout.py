from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class GeminiHomeLayout:
    home_root: Path
    gemini_dir: Path
    settings_path: Path
    trusted_folders_path: Path
    tmp_root: Path


def gemini_layout_for_home(home_root: Path) -> GeminiHomeLayout:
    root = Path(home_root).expanduser()
    gemini_dir = root / '.gemini'
    return GeminiHomeLayout(
        home_root=root,
        gemini_dir=gemini_dir,
        settings_path=gemini_dir / 'settings.json',
        trusted_folders_path=gemini_dir / 'trustedFolders.json',
        tmp_root=gemini_dir / 'tmp',
    )


def current_gemini_home_root() -> Path:
    root = _env_root()
    if root is not None:
        home_root = _home_root_from_tmp_root(root)
        if home_root is not None:
            return home_root
    return Path.home().expanduser()


def current_gemini_tmp_root() -> Path:
    root = _env_root()
    if root is not None:
        return root
    return gemini_layout_for_home(Path.home()).tmp_root


def gemini_layout_from_session_data(data: dict[str, object] | None) -> GeminiHomeLayout | None:
    if not isinstance(data, dict):
        return None
    home_root = _path_or_none(data.get('gemini_home'))
    if home_root is not None:
        return gemini_layout_for_home(home_root)

    tmp_root = _path_or_none(data.get('gemini_root'))
    if tmp_root is not None:
        home_root = _home_root_from_tmp_root(tmp_root)
        if home_root is not None:
            return gemini_layout_for_home(home_root)

    session_path = _path_or_none(data.get('gemini_session_path'))
    if session_path is not None:
        home_root = _home_root_from_session_path(session_path)
        if home_root is not None:
            return gemini_layout_for_home(home_root)
    return None


def _env_root() -> Path | None:
    raw = str(os.environ.get('GEMINI_ROOT') or '').strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser()
    except Exception:
        return None


def _home_root_from_tmp_root(tmp_root: Path) -> Path | None:
    root = Path(tmp_root).expanduser()
    if root.name != 'tmp':
        return None
    parent = root.parent
    if parent.name == '.gemini':
        return parent.parent
    return None


def _home_root_from_session_path(session_path: Path) -> Path | None:
    candidate = Path(session_path).expanduser()
    for parent in candidate.parents:
        if parent.name == '.gemini':
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
    'GeminiHomeLayout',
    'current_gemini_home_root',
    'current_gemini_tmp_root',
    'gemini_layout_for_home',
    'gemini_layout_from_session_data',
]
