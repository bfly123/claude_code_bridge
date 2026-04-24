from __future__ import annotations

import importlib
from pathlib import Path

from agents.models import parse_layout_spec

from ..common import ConfigLoadResult, ConfigValidationError
from ..parsing import validate_project_config
from ..paths import project_config_path


def _build_compact_agent_record(provider: str, *, workspace_mode: str) -> dict[str, str]:
    return {
        'provider': provider,
        'target': '.',
        'workspace_mode': workspace_mode,
        'restore': 'auto',
        'permission': 'manual',
    }


def _strip_layout_comments(line: str) -> str:
    return line.split('#', 1)[0].split('//', 1)[0].strip()


def _normalize_compact_layout_text(text: str) -> str:
    return '\n'.join(
        cleaned
        for cleaned in (_strip_layout_comments(line) for line in text.splitlines())
        if cleaned
    ).strip()


def _raise_invalid_compact_token(path: Path, token: str) -> None:
    raise ConfigValidationError(
        f"{path}: invalid token {token!r}; expected 'agent_name:provider' or 'cmd'"
    )


def _consume_compact_leaf(
    leaf,
    *,
    path: Path,
    default_agents: list[str],
    agents: dict[str, dict[str, str]],
    cmd_enabled: bool,
) -> bool:
    token = leaf.name.strip()
    normalized_name = token.lower()
    if normalized_name == 'cmd':
        if leaf.provider is not None:
            raise ConfigValidationError(f"{path}: reserved token 'cmd' cannot declare a provider")
        if cmd_enabled:
            raise ConfigValidationError(f'{path}: compact config cannot define cmd more than once')
        return True
    if leaf.provider is None:
        _raise_invalid_compact_token(path, token)
    if normalized_name in agents:
        raise ConfigValidationError(f'{path}: duplicate agent name in compact config: {token}')
    default_agents.append(token)
    agents[normalized_name] = _build_compact_agent_record(
        leaf.provider,
        workspace_mode='git-worktree' if str(leaf.workspace_mode or '').strip() == 'worktree' else 'inplace',
    )
    return cmd_enabled


def _parse_compact_config_document(text: str, *, path: Path) -> dict[str, object]:
    layout_text = _normalize_compact_layout_text(text)
    if not layout_text:
        raise ConfigValidationError(f'{path}: config is empty')
    try:
        layout = parse_layout_spec(layout_text)
    except Exception as exc:
        raise ConfigValidationError(f'{path}: invalid compact layout: {exc}') from exc

    default_agents: list[str] = []
    agents: dict[str, dict[str, str]] = {}
    cmd_enabled = False
    for leaf in layout.iter_leaves():
        cmd_enabled = _consume_compact_leaf(
            leaf,
            path=path,
            default_agents=default_agents,
            agents=agents,
            cmd_enabled=cmd_enabled,
        )
    if not default_agents:
        raise ConfigValidationError(f'{path}: compact config must define at least one agent')

    return {
        'version': 2,
        'default_agents': default_agents,
        'agents': agents,
        'cmd_enabled': cmd_enabled,
        'layout': layout.render(),
    }


def _looks_like_rich_config(text: str) -> bool:
    for line in text.splitlines():
        body = line.split('#', 1)[0].strip()
        if not body:
            continue
        if body.startswith('[') or '=' in body:
            return True
    return False


def _import_optional_toml_reader():
    for module_name in ('tomllib', 'tomli', 'toml'):
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
    return None


def _load_toml_reader(path: Path):
    reader = _import_optional_toml_reader()
    if reader is None:
        raise ConfigValidationError(
            f'{path}: rich TOML config requires Python 3.11+ or an installed tomli/toml parser'
        )
    loads = getattr(reader, 'loads', None)
    if not callable(loads):  # pragma: no cover - defensive guard for unexpected parser shims
        raise ConfigValidationError(f'{path}: TOML parser does not expose a supported loads() entrypoint')
    return loads


def _parse_toml_config_document(text: str, *, path: Path) -> dict[str, object]:
    try:
        document = _load_toml_reader(path)(text)
    except Exception as exc:
        if isinstance(exc, ConfigValidationError):
            raise
        raise ConfigValidationError(f'{path}: invalid TOML config: {exc}') from exc
    if not isinstance(document, dict):
        raise ConfigValidationError(f'{path}: TOML config must decode to a table/object')
    return dict(document)


def _load_config_document(path: Path) -> dict[str, object]:
    text = path.read_text(encoding='utf-8')
    if _looks_like_rich_config(text):
        return _parse_toml_config_document(text, path=path)
    return _parse_compact_config_document(text, path=path)


def load_project_config(project_root: Path) -> ConfigLoadResult:
    project_path = project_config_path(project_root)
    if project_path.exists():
        return ConfigLoadResult(
            config=validate_project_config(_load_config_document(project_path), source_path=project_path),
            source_path=project_path,
            used_default=False,
        )
    raise ConfigValidationError(f'config not found for project {project_root}')


__all__ = ['load_project_config']
