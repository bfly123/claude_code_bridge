from __future__ import annotations

import json
from pathlib import Path
import shutil

from provider_profiles import provider_api_env_keys

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
    materialize_gemini_home_config(layout.home_root, profile=profile)
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


def materialize_gemini_home_config(target_home: Path, *, profile=None, source_home: Path | None = None) -> GeminiHomeLayout:
    layout = gemini_layout_for_home(target_home)
    _prepare_managed_home(layout)
    source_root = Path(source_home).expanduser() if source_home is not None else _system_home_root()
    if layout.home_root != source_root:
        _materialize_settings(source_root, layout, profile=profile)
        _materialize_trusted_folders(source_root, layout)
        _materialize_auth(source_root, layout, profile=profile)
    return layout


def _materialize_settings(source_home: Path, layout: GeminiHomeLayout, *, profile) -> None:
    projected = _projected_settings_payload(source_home / '.gemini' / 'settings.json', profile=profile)
    existing = _read_json_object(layout.settings_path)
    merged = _merge_settings_payload(projected, existing=existing)
    if merged is None:
        return
    _write_json_object(layout.settings_path, merged)


def _materialize_trusted_folders(source_home: Path, layout: GeminiHomeLayout) -> None:
    projected = _read_json_object(source_home / '.gemini' / 'trustedFolders.json')
    existing = _read_json_object(layout.trusted_folders_path)
    merged = _merge_object_payload(projected, existing=existing)
    if merged is None:
        return
    _write_json_object(layout.trusted_folders_path, merged)


def _materialize_auth(source_home: Path, layout: GeminiHomeLayout, *, profile) -> None:
    target_auth = layout.gemini_dir / 'oauth_creds.json'
    if not _should_project_oauth_credentials(source_home / '.gemini' / 'settings.json', profile=profile):
        _remove_file(target_auth)
        return
    _sync_file(source_home / '.gemini' / 'oauth_creds.json', target_auth)


def _projected_settings_payload(source_settings_path: Path, *, profile) -> dict[str, object] | None:
    source_payload = _read_json_object(source_settings_path)
    if not source_payload:
        return {} if _needs_settings_stub(profile) else None

    source_env = dict(source_payload.get('env') or {}) if isinstance(source_payload.get('env'), dict) else {}
    env_payload = dict(source_env) if _inherits_config(profile) else {}
    if _inherits_api(profile):
        for key in provider_api_env_keys('gemini'):
            value = source_env.get(key)
            if value is not None:
                env_payload[key] = value
    else:
        for key in provider_api_env_keys('gemini'):
            env_payload.pop(key, None)

    payload: dict[str, object] = dict(source_payload) if _inherits_config(profile) else {}
    projected_selected_type = _projected_auth_selected_type(_selected_auth_type(source_payload), profile=profile)
    if projected_selected_type is not None:
        _set_selected_auth_type(payload, projected_selected_type)
    else:
        _clear_selected_auth_type(payload)
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
    existing: dict[str, object] | None,
) -> dict[str, object] | None:
    projected_payload = dict(projected or {})
    existing_payload = dict(existing or {})
    merged = dict(projected_payload)
    hooks = existing_payload.get('hooks')
    if hooks is not None:
        merged['hooks'] = hooks
    if merged:
        return merged
    if existing_payload:
        return existing_payload
    return None


def _merge_object_payload(
    projected: dict[str, object] | None,
    *,
    existing: dict[str, object] | None,
) -> dict[str, object] | None:
    merged = dict(projected or {})
    merged.update(dict(existing or {}))
    return merged if merged else None


def _read_json_object(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _write_json_object(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _needs_settings_stub(profile) -> bool:
    return bool(_inherits_api(profile) or _inherits_auth(profile) or _inherits_config(profile))


def _inherits_api(profile) -> bool:
    return True if profile is None else bool(getattr(profile, 'inherit_api', True))


def _inherits_auth(profile) -> bool:
    return True if profile is None else bool(getattr(profile, 'inherit_auth', True))


def _inherits_config(profile) -> bool:
    return True if profile is None else bool(getattr(profile, 'inherit_config', True))


def _should_project_oauth_credentials(source_settings_path: Path, *, profile) -> bool:
    if not _inherits_auth(profile):
        return False
    selected_type = _selected_auth_type(_read_json_object(source_settings_path))
    return selected_type in {'oauth-personal'}


def _selected_auth_type(payload: dict[str, object] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    security = payload.get('security')
    if not isinstance(security, dict):
        return None
    auth = security.get('auth')
    if not isinstance(auth, dict):
        return None
    raw = str(auth.get('selectedType') or '').strip()
    return raw or None


def _projected_auth_selected_type(selected_type: str | None, *, profile) -> str | None:
    normalized = str(selected_type or '').strip()
    if not normalized:
        return None
    if normalized in {'oauth-personal', 'compute-default-credentials'}:
        return normalized if _inherits_auth(profile) else None
    if normalized in {'gemini-api-key', 'vertex-ai'}:
        return normalized if _inherits_api(profile) else None
    return normalized if (_inherits_api(profile) or _inherits_auth(profile)) else None


def _set_selected_auth_type(payload: dict[str, object], selected_type: str) -> None:
    security = payload.get('security')
    if not isinstance(security, dict):
        security = {}
    auth = security.get('auth')
    if not isinstance(auth, dict):
        auth = {}
    auth['selectedType'] = selected_type
    security['auth'] = auth
    payload['security'] = security


def _clear_selected_auth_type(payload: dict[str, object]) -> None:
    security = payload.get('security')
    if not isinstance(security, dict):
        return
    auth = security.get('auth')
    if isinstance(auth, dict):
        auth.pop('selectedType', None)
        if auth:
            security['auth'] = auth
        else:
            security.pop('auth', None)
    if security:
        payload['security'] = security
    else:
        payload.pop('security', None)


def _sync_file(source: Path, target: Path) -> None:
    if not source.is_file():
        _remove_file(target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, target)
    except Exception:
        pass


def _remove_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except Exception:
        return


def _system_home_root() -> Path:
    return Path.home().expanduser()


__all__ = [
    'materialize_gemini_home_config',
    'prepare_gemini_home_overrides',
    'resolve_gemini_home_layout',
]
