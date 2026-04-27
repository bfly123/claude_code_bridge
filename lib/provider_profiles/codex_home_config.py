from __future__ import annotations

import hashlib
import importlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
import re
import shutil


_CODEX_CUSTOM_PROVIDER_ID = 'custom'
_BARE_TOML_KEY_RE = re.compile(r'^[A-Za-z0-9_-]+$')


@dataclass(frozen=True)
class CodexApiAuthority:
    provider_id: str
    base_url: str
    wire_api: str = 'responses'
    requires_openai_auth: bool = False


def materialize_codex_home_config(
    target_home: Path,
    *,
    profile=None,
    source_home: Path | None = None,
) -> Path:
    target_home = Path(target_home).expanduser()
    source_home = Path(source_home).expanduser() if source_home is not None else _system_codex_home()
    target_home.mkdir(parents=True, exist_ok=True)
    (target_home / 'sessions').mkdir(parents=True, exist_ok=True)

    target_config = target_home / 'config.toml'
    source_config = source_home / 'config.toml'
    authority = codex_api_authority(profile)

    if authority is not None:
        _write_codex_api_authority_config(target_config, authority, source_config=source_config)
    elif _inherits_config(profile) and _inherits_api(profile) and _source_config_valid(source_config):
        if source_config.is_file():
            _sync_file(source_config, target_config)
        else:
            _write_managed_config_stub(target_config)
    else:
        _write_managed_config_stub(target_config)

    _materialize_auth_file(
        source_home / 'auth.json',
        target_home / 'auth.json',
        profile=profile,
        authority=authority,
    )
    _sync_tree(source_home / 'skills', target_home / 'skills', enabled=_inherits_skills(profile))
    _sync_tree(source_home / 'commands', target_home / 'commands', enabled=_inherits_commands(profile))
    return target_config


def codex_api_authority(profile) -> CodexApiAuthority | None:
    if profile is None or _inherits_api(profile):
        return None
    env = _profile_env(profile)
    base_url = env.get('OPENAI_BASE_URL') or env.get('OPENAI_API_BASE') or ''
    if not base_url:
        return None
    return CodexApiAuthority(
        provider_id=_CODEX_CUSTOM_PROVIDER_ID,
        base_url=base_url,
    )


def codex_provider_authority_fingerprint(profile) -> str | None:
    authority = codex_api_authority(profile)
    if authority is None:
        return None
    payload = {
        'provider_id': authority.provider_id,
        'base_url': authority.base_url,
        'wire_api': authority.wire_api,
        'requires_openai_auth': authority.requires_openai_auth,
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()[:16]


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


def _profile_env(profile) -> dict[str, str]:
    if profile is None:
        return {}
    return {
        str(key): str(value).strip()
        for key, value in dict(getattr(profile, 'env', {}) or {}).items()
        if str(value).strip()
    }


def _explicit_api_key(profile) -> str:
    return _profile_env(profile).get('OPENAI_API_KEY', '')


def _write_codex_api_authority_config(target: Path, authority: CodexApiAuthority, *, source_config: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _managed_codex_config_payload(source_config, authority=authority)
    target.write_text(_render_toml_document(payload), encoding='utf-8')


def _write_managed_config_stub(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('# ccb agent-local codex config\n', encoding='utf-8')


def _managed_codex_config_payload(source_config: Path, *, authority: CodexApiAuthority) -> dict[str, object]:
    payload = {'model_provider': authority.provider_id}
    inherited_payload = _strip_route_authority(_read_source_config_payload(source_config))
    for key, value in inherited_payload.items():
        payload[key] = value
    payload['model_providers'] = {
        authority.provider_id: {
            'name': authority.provider_id,
            'wire_api': authority.wire_api,
            'requires_openai_auth': authority.requires_openai_auth,
            'base_url': authority.base_url,
        }
    }
    return payload


def _import_optional_toml_reader():
    for module_name in ('tomllib', 'tomli', 'toml'):
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
    return None


def _read_source_config_payload(config_path: Path) -> dict[str, object]:
    try:
        if not config_path.is_file():
            return {}
        reader = _import_optional_toml_reader()
        if reader is None:
            return {}
        if getattr(reader, '__name__', '') == 'toml':
            payload = reader.loads(config_path.read_text(encoding='utf-8'))
        elif hasattr(reader, 'load'):
            with config_path.open('rb') as handle:
                payload = reader.load(handle)
        elif hasattr(reader, 'loads'):  # pragma: no cover - defensive fallback
            payload = reader.loads(config_path.read_text(encoding='utf-8'))
        else:  # pragma: no cover - unsupported parser shim
            return {}
    except Exception:
        return {}
    return _clone_mapping(payload) if isinstance(payload, dict) else {}


def _source_config_valid(config_path: Path) -> bool:
    try:
        if not config_path.is_file():
            return True
        reader = _import_optional_toml_reader()
        if reader is None:
            return True
        if getattr(reader, '__name__', '') == 'toml':
            reader.loads(config_path.read_text(encoding='utf-8'))
        elif hasattr(reader, 'load'):
            with config_path.open('rb') as handle:
                reader.load(handle)
        elif hasattr(reader, 'loads'):  # pragma: no cover - defensive fallback
            reader.loads(config_path.read_text(encoding='utf-8'))
        else:  # pragma: no cover - unsupported parser shim
            return True
        return True
    except Exception:
        return False


def _strip_route_authority(payload: dict[str, object]) -> dict[str, object]:
    cleaned: dict[str, object] = {}
    for raw_key, value in payload.items():
        key = str(raw_key)
        if key in {'model_provider', 'model_providers'}:
            continue
        cleaned[key] = _clone_payload(value)
    return cleaned


def _clone_mapping(payload: dict[str, object]) -> dict[str, object]:
    return {str(key): _clone_payload(value) for key, value in payload.items()}


def _clone_payload(value: object) -> object:
    if isinstance(value, dict):
        return _clone_mapping(value)
    if isinstance(value, list):
        return [_clone_payload(item) for item in value]
    return value


def _materialize_auth_file(source: Path, target: Path, *, profile, authority: CodexApiAuthority | None) -> None:
    if authority is not None:
        explicit_key = _explicit_api_key(profile)
        if explicit_key:
            _write_auth_file(target, explicit_key)
        else:
            target.unlink(missing_ok=True)
        return
    _sync_auth_file(source, target, profile=profile)


def _sync_auth_file(source: Path, target: Path, *, profile) -> None:
    if not _inherits_auth(profile) or not source.is_file():
        target.unlink(missing_ok=True)
        return
    _sync_file(source, target)


def _write_auth_file(target: Path, api_key: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({'OPENAI_API_KEY': api_key}, ensure_ascii=False, separators=(',', ':'))
    target.write_text(f'{payload}\n', encoding='utf-8')


def _sync_file(source: Path, target: Path) -> None:
    if not source.is_file():
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, target)
    except Exception:
        pass


def _sync_tree(source: Path, target: Path, *, enabled: bool) -> None:
    if not enabled:
        _remove_path(target)
        return
    if not source.is_dir():
        _remove_path(target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(source, target, dirs_exist_ok=True)
    except Exception:
        pass


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def _system_codex_home() -> Path:
    return Path(os.environ.get('CODEX_HOME') or (Path.home() / '.codex')).expanduser()


def _render_toml_document(payload: dict[str, object]) -> str:
    sections = _render_toml_sections(payload, path=())
    rendered = '\n\n'.join(section for section in sections if section.strip())
    return f'{rendered}\n' if rendered else ''


def _render_toml_sections(payload: dict[str, object], *, path: tuple[str, ...]) -> list[str]:
    scalar_lines: list[str] = []
    child_sections: list[str] = []
    child_tables: list[tuple[str, dict[str, object]]] = []
    for raw_key, value in payload.items():
        key = str(raw_key)
        if value is None:
            continue
        if isinstance(value, dict):
            child_tables.append((key, value))
            continue
        scalar_lines.append(f'{_render_toml_key(key)} = {_render_toml_value(value)}')

    sections: list[str] = []
    if path:
        header = f'[{_render_toml_path(path)}]'
        if scalar_lines:
            sections.append('\n'.join([header, *scalar_lines]))
        elif not child_tables:
            sections.append(header)
    elif scalar_lines:
        sections.append('\n'.join(scalar_lines))

    for key, child in child_tables:
        child_sections.extend(_render_toml_sections(child, path=(*path, key)))
    sections.extend(child_sections)
    return sections


def _render_toml_path(path: tuple[str, ...]) -> str:
    return '.'.join(_render_toml_key_part(part) for part in path)


def _render_toml_key(key: str) -> str:
    return _render_toml_key_part(key)


def _render_toml_key_part(key: str) -> str:
    return key if _BARE_TOML_KEY_RE.fullmatch(key) else json.dumps(key)


def _render_toml_value(value: object) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return '[' + ', '.join(_render_toml_value(item) for item in value) + ']'
    raise TypeError(f'unsupported TOML value type: {type(value).__name__}')


__all__ = [
    'CodexApiAuthority',
    'codex_api_authority',
    'codex_provider_authority_fingerprint',
    'materialize_codex_home_config',
]
