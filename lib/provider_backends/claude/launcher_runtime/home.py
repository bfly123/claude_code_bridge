from __future__ import annotations

import json
from pathlib import Path
import shutil

from provider_profiles import provider_api_env_keys

from ..home_layout import ClaudeHomeLayout, claude_layout_for_home, claude_layout_from_session_data
from .session_paths import read_session_payload, session_file_for_runtime_dir, state_dir_for_runtime_dir


def resolve_claude_home_layout(runtime_dir: Path, profile) -> ClaudeHomeLayout:
    explicit_runtime_home = _profile_runtime_home(profile)
    if explicit_runtime_home is not None:
        return claude_layout_for_home(explicit_runtime_home)

    managed_home = _managed_isolated_home(runtime_dir)
    existing = _existing_layout(runtime_dir, managed_home=managed_home)
    if existing is not None:
        return existing

    return claude_layout_for_home(managed_home)


def prepare_claude_home_overrides(runtime_dir: Path, profile) -> dict[str, str]:
    layout = resolve_claude_home_layout(runtime_dir, profile)
    materialize_claude_home_config(layout.home_root, profile=profile)
    return {
        'HOME': str(layout.home_root),
        'CLAUDE_PROJECTS_ROOT': str(layout.projects_root),
        'CLAUDE_PROJECT_ROOT': str(layout.projects_root),
    }


def materialize_claude_home_config(target_home: Path, *, profile=None, source_home: Path | None = None) -> ClaudeHomeLayout:
    layout = claude_layout_for_home(Path(target_home).expanduser())
    source_root = Path(source_home).expanduser() if source_home is not None else _system_home_root()
    _prepare_managed_home(source_root, layout, profile=profile)
    return layout


def _profile_runtime_home(profile) -> Path | None:
    runtime_home = getattr(profile, 'runtime_home', None) if profile is not None else None
    if not runtime_home:
        return None
    return Path(runtime_home).expanduser()


def _existing_layout(runtime_dir: Path, *, managed_home: Path) -> ClaudeHomeLayout | None:
    session_file = session_file_for_runtime_dir(runtime_dir)
    if session_file is None or not session_file.is_file():
        return None
    data = read_session_payload(session_file)
    if not isinstance(data, dict):
        return None
    layout = claude_layout_from_session_data(data)
    if layout is None:
        return None
    return layout if _is_within_home_root(layout.home_root, managed_home) else None


def _managed_isolated_home(runtime_dir: Path) -> Path:
    state_dir = state_dir_for_runtime_dir(runtime_dir)
    if state_dir is not None:
        return state_dir / 'home'
    return Path(runtime_dir).expanduser() / 'claude-home'


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


def _prepare_managed_home(source_home: Path, target_layout: ClaudeHomeLayout, *, profile) -> None:
    target_layout.home_root.mkdir(parents=True, exist_ok=True)
    target_layout.claude_dir.mkdir(parents=True, exist_ok=True)
    target_layout.projects_root.mkdir(parents=True, exist_ok=True)
    target_layout.session_env_root.mkdir(parents=True, exist_ok=True)

    if target_layout.home_root == source_home.expanduser():
        _ensure_trust_file(target_layout.trust_path)
        return

    _materialize_settings(source_home, target_layout, profile=profile)
    _materialize_trust(source_home, target_layout)
    if _inherits_commands(profile):
        _copytree_if_missing(source_home / '.claude' / 'commands', target_layout.claude_dir / 'commands')
    if _inherits_skills(profile):
        _copy_if_missing(source_home / '.claude' / 'CLAUDE.md', target_layout.claude_dir / 'CLAUDE.md')


def _materialize_settings(source_home: Path, target_layout: ClaudeHomeLayout, *, profile) -> None:
    payload = _projected_settings_payload(source_home / '.claude' / 'settings.json', profile=profile)
    existing = _read_json_object(target_layout.settings_path)
    merged = _merge_settings_payload(payload, existing=existing)
    if merged is None:
        return
    target_layout.settings_path.parent.mkdir(parents=True, exist_ok=True)
    target_layout.settings_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )


def _materialize_trust(source_home: Path, target_layout: ClaudeHomeLayout) -> None:
    source_trust = source_home / '.claude.json'
    if not target_layout.trust_path.exists() and source_trust.is_file():
        _copy_if_missing(source_trust, target_layout.trust_path)
    _ensure_trust_file(target_layout.trust_path)


def _projected_settings_payload(source_settings_path: Path, *, profile) -> dict[str, object] | None:
    source_payload = _read_json_object(source_settings_path)
    if not source_payload:
        return {} if _needs_settings_stub(profile) else None

    env_payload = dict(source_payload.get('env') or {}) if isinstance(source_payload.get('env'), dict) else {}
    if not _inherits_api(profile):
        for key in provider_api_env_keys('claude'):
            env_payload.pop(key, None)
    elif not _inherits_auth(profile):
        env_payload.pop('ANTHROPIC_AUTH_TOKEN', None)
        env_payload.pop('ANTHROPIC_API_KEY', None)

    include_config = _inherits_config(profile)
    payload: dict[str, object] = {}
    if include_config:
        payload.update(source_payload)
    if env_payload:
        payload['env'] = env_payload
    else:
        payload.pop('env', None)
    if payload:
        return payload
    return {} if _needs_settings_stub(profile) else None


def _merge_settings_payload(
    projected: dict[str, object] | None,
    *,
    existing: dict[str, object],
) -> dict[str, object] | None:
    existing_payload = dict(existing or {})
    projected_payload = dict(projected or {})
    merged = dict(projected_payload)

    for key in ('hooks', 'permissions'):
        value = existing_payload.get(key)
        if value is not None:
            merged[key] = value

    if not merged and existing_payload:
        return existing_payload
    if merged:
        return merged
    return None


def _needs_settings_stub(profile) -> bool:
    return bool(_inherits_api(profile) or _inherits_auth(profile) or _inherits_config(profile))


def _inherits_api(profile) -> bool:
    return True if profile is None else bool(getattr(profile, 'inherit_api', True))


def _inherits_auth(profile) -> bool:
    return True if profile is None else bool(getattr(profile, 'inherit_auth', True))


def _inherits_config(profile) -> bool:
    return True if profile is None else bool(getattr(profile, 'inherit_config', True))


def _inherits_skills(profile) -> bool:
    return True if profile is None else bool(getattr(profile, 'inherit_skills', True))


def _inherits_commands(profile) -> bool:
    return True if profile is None else bool(getattr(profile, 'inherit_commands', True))


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _ensure_trust_file(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{}\n', encoding='utf-8')


def _copy_if_missing(source: Path, target: Path) -> None:
    if target.exists() or not source.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, target)
    except Exception:
        pass


def _copytree_if_missing(source: Path, target: Path) -> None:
    if target.exists() or not source.is_dir():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(source, target)
    except Exception:
        pass


def _system_home_root() -> Path:
    return Path.home().expanduser()


__all__ = ['materialize_claude_home_config', 'prepare_claude_home_overrides', 'resolve_claude_home_layout']
