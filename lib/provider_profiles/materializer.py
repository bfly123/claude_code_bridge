from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.models import AgentSpec
from provider_profiles.models import ProviderProfileSpec, ResolvedProviderProfile
from storage.atomic import atomic_write_json
from storage.paths import PathLayout


_API_ENV_KEYS = {
    'codex': {
        'OPENAI_API_KEY',
        'OPENAI_BASE_URL',
        'OPENAI_API_BASE',
        'OPENAI_ORG_ID',
        'OPENAI_ORGANIZATION',
    },
    'claude': {'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL'},
    'gemini': {'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'GOOGLE_API_BASE', 'GOOGLE_GENAI_USE_VERTEXAI'},
}


def materialize_provider_profile(
    *,
    layout: PathLayout,
    spec: 'AgentSpec',
    workspace_path: Path,
) -> ResolvedProviderProfile:
    del workspace_path
    runtime_dir = layout.agent_provider_runtime_dir(spec.name, spec.provider)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    profile_spec = spec.provider_profile
    profile_root = _resolve_profile_root(layout.project_root, spec, profile_spec)

    if spec.provider == 'codex':
        profile = _materialize_codex_profile(
            spec=spec,
            profile_spec=profile_spec,
            profile_root=profile_root,
        )
    elif spec.provider in {'claude', 'gemini'}:
        profile = _materialize_api_profile(
            spec=spec,
            profile_spec=profile_spec,
            profile_root=profile_root,
        )
    else:
        profile = ResolvedProviderProfile(
            provider=spec.provider,
            agent_name=spec.name,
            mode=profile_spec.mode,
            profile_root=str(profile_root) if profile_root is not None else None,
            runtime_home=None,
            env=dict(profile_spec.env),
            inherit_api=profile_spec.inherit_api,
            inherit_auth=profile_spec.inherit_auth,
            inherit_config=profile_spec.inherit_config,
            inherit_skills=profile_spec.inherit_skills,
            inherit_commands=profile_spec.inherit_commands,
        )

    _write_profile_record(runtime_dir, profile)
    return profile


def load_resolved_provider_profile(runtime_dir: Path) -> ResolvedProviderProfile | None:
    path = Path(runtime_dir) / 'provider-profile.json'
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    try:
        return ResolvedProviderProfile.from_record(data)
    except Exception:
        return None


def provider_api_env_keys(provider: str) -> set[str]:
    return set(_API_ENV_KEYS.get(str(provider or '').strip().lower(), set()))


def _materialize_codex_profile(
    *,
    spec: 'AgentSpec',
    profile_spec: ProviderProfileSpec,
    profile_root: Path,
) -> ResolvedProviderProfile:
    needs_runtime_home = profile_spec.mode != 'inherit' or profile_spec.home is not None or bool(profile_spec.env)
    runtime_home = None
    if needs_runtime_home:
        runtime_home = profile_root
        runtime_home.mkdir(parents=True, exist_ok=True)
        (runtime_home / 'sessions').mkdir(parents=True, exist_ok=True)
        source_home = _system_codex_home()
        if profile_spec.inherit_config:
            _copy_if_missing(source_home / 'config.toml', runtime_home / 'config.toml')
        elif not (runtime_home / 'config.toml').exists():
            (runtime_home / 'config.toml').write_text('# ccb agent-local codex config\n', encoding='utf-8')
        if profile_spec.inherit_auth:
            _copy_if_missing(source_home / 'auth.json', runtime_home / 'auth.json')
        if profile_spec.inherit_skills:
            _copytree_if_missing(source_home / 'skills', runtime_home / 'skills')
        if profile_spec.inherit_commands:
            _copytree_if_missing(source_home / 'commands', runtime_home / 'commands')

    return ResolvedProviderProfile(
        provider=spec.provider,
        agent_name=spec.name,
        mode=profile_spec.mode,
        profile_root=str(profile_root),
        runtime_home=str(runtime_home) if runtime_home is not None else None,
        env=dict(profile_spec.env),
        inherit_api=profile_spec.inherit_api,
        inherit_auth=profile_spec.inherit_auth,
        inherit_config=profile_spec.inherit_config,
        inherit_skills=profile_spec.inherit_skills,
        inherit_commands=profile_spec.inherit_commands,
    )


def _materialize_api_profile(
    *,
    spec: 'AgentSpec',
    profile_spec: ProviderProfileSpec,
    profile_root: Path,
) -> ResolvedProviderProfile:
    api_keys = provider_api_env_keys(spec.provider)
    env = {key: value for key, value in profile_spec.env.items() if key in api_keys or profile_spec.mode != 'inherit'}
    return ResolvedProviderProfile(
        provider=spec.provider,
        agent_name=spec.name,
        mode=profile_spec.mode,
        profile_root=str(profile_root),
        runtime_home=None,
        env=env,
        inherit_api=profile_spec.inherit_api,
        inherit_auth=profile_spec.inherit_auth,
        inherit_config=profile_spec.inherit_config,
        inherit_skills=profile_spec.inherit_skills,
        inherit_commands=profile_spec.inherit_commands,
    )


def _resolve_profile_root(project_root: Path, spec: AgentSpec, profile_spec: ProviderProfileSpec) -> Path:
    if profile_spec.home:
        raw = Path(profile_spec.home).expanduser()
        if not raw.is_absolute():
            raw = Path(project_root) / raw
        return raw.resolve()
    return (Path(project_root) / '.ccb' / 'provider-profiles' / spec.name / spec.provider).resolve()


def _write_profile_record(runtime_dir: Path, profile: ResolvedProviderProfile) -> Path:
    path = Path(runtime_dir) / 'provider-profile.json'
    atomic_write_json(path, profile.to_record())
    return path


def _system_codex_home() -> Path:
    return Path(os.environ.get('CODEX_HOME') or (Path.home() / '.codex')).expanduser()


def _copy_if_missing(source: Path, target: Path) -> None:
    if target.exists() or not source.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copytree_if_missing(source: Path, target: Path) -> None:
    if target.exists() or not source.is_dir():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


__all__ = ['load_resolved_provider_profile', 'materialize_provider_profile', 'provider_api_env_keys']
