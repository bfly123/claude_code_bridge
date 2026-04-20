from __future__ import annotations

import json
from pathlib import Path
import shutil

from ..home_layout import GeminiHomeLayout, gemini_layout_for_home, gemini_layout_from_session_data
from .session_paths import read_session_payload, session_file_for_runtime_dir, state_dir_for_runtime_dir


def resolve_gemini_home_layout(runtime_dir: Path, profile) -> GeminiHomeLayout:
    explicit_runtime_home = _profile_runtime_home(profile)
    if explicit_runtime_home is not None:
        return gemini_layout_for_home(explicit_runtime_home)

    managed_home = _managed_isolated_home(runtime_dir)
    existing = _existing_layout(runtime_dir, managed_home=managed_home)
    if existing is not None:
        return existing

    return gemini_layout_for_home(managed_home)


def prepare_gemini_home_overrides(runtime_dir: Path, profile) -> dict[str, str]:
    layout = resolve_gemini_home_layout(runtime_dir, profile)
    _prepare_managed_home(layout)
    return {
        'HOME': str(layout.home_root),
        'GEMINI_ROOT': str(layout.tmp_root),
    }


def _profile_runtime_home(profile) -> Path | None:
    runtime_home = getattr(profile, 'runtime_home', None) if profile is not None else None
    if not runtime_home:
        return None
    return Path(runtime_home).expanduser()


def _existing_layout(runtime_dir: Path, *, managed_home: Path) -> GeminiHomeLayout | None:
    session_file = session_file_for_runtime_dir(runtime_dir)
    if session_file is None or not session_file.is_file():
        return None
    data = read_session_payload(session_file)
    if not isinstance(data, dict):
        return None
    layout = gemini_layout_from_session_data(data)
    if layout is None:
        return None
    return layout if _is_within_home_root(layout.home_root, managed_home) else None


def _managed_isolated_home(runtime_dir: Path) -> Path:
    state_dir = state_dir_for_runtime_dir(runtime_dir)
    if state_dir is not None:
        return state_dir / 'home'
    return Path(runtime_dir).expanduser() / 'gemini-home'


def _is_within_home_root(candidate: Path, managed_home: Path) -> bool:
    normalized_candidate = _normalize_path(candidate)
    normalized_managed = _normalize_path(managed_home)
    if normalized_candidate is None or normalized_managed is None:
        return False
    try:
        normalized_candidate.relative_to(normalized_managed)
        return True
    except Exception:
        return False


def _normalize_path(value: object) -> Path | None:
    try:
        return Path(value).expanduser().resolve()
    except Exception:
        try:
            return Path(value).expanduser()
        except Exception:
            return None


def _prepare_managed_home(layout: GeminiHomeLayout) -> None:
    layout.home_root.mkdir(parents=True, exist_ok=True)
    layout.gemini_dir.mkdir(parents=True, exist_ok=True)
    layout.tmp_root.mkdir(parents=True, exist_ok=True)
    _ensure_json_file(layout.settings_path)
    _ensure_json_file(layout.trusted_folders_path)


def _ensure_json_file(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{}\n', encoding='utf-8')


def materialize_gemini_home_config(target_home: Path, *, source_home: Path | None = None) -> None:
    layout = gemini_layout_for_home(target_home)
    _prepare_managed_home(layout)
    if source_home is None:
        return
    source_home = Path(source_home).expanduser()
    _copy_if_missing(source_home / '.gemini' / 'settings.json', layout.settings_path)
    _copy_if_missing(source_home / '.gemini' / 'trustedFolders.json', layout.trusted_folders_path)


def _copy_if_missing(source: Path, target: Path) -> None:
    if target.exists() or not source.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, target)
    except Exception:
        payload = _read_json_object(source)
        if payload is None:
            return
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _read_json_object(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


__all__ = [
    'materialize_gemini_home_config',
    'prepare_gemini_home_overrides',
    'resolve_gemini_home_layout',
]
