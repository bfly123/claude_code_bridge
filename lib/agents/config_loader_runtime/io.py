from __future__ import annotations

from pathlib import Path
import re

from agents.models import ProjectConfig
from agents.store import AgentSpecStore
from storage.atomic import atomic_write_text
from storage.paths import PathLayout

from agents.models import parse_layout_spec

from .common import CONFIG_FILENAME, ConfigLoadResult, ConfigValidationError
from .defaults import render_default_project_config_text, render_project_config_text
from .parsing import validate_project_config
from .paths import project_config_path

try:  # pragma: no branch
    import tomllib as _toml_reader
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    try:
        import tomli as _toml_reader  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover - external fallback
        import toml as _toml_reader  # type: ignore[no-redef]

_COMPACT_ENTRY_RE = re.compile(r'^(?P<agent>[A-Za-z][A-Za-z0-9_-]{0,31})\s*:\s*(?P<provider>[A-Za-z0-9_-]+)$')


def _build_compact_agent_record(provider: str) -> dict[str, str]:
    return {
        'provider': provider,
        'target': '.',
        'workspace_mode': 'git-worktree',
        'restore': 'auto',
        'permission': 'manual',
    }


def _parse_compact_config_document(text: str, *, path: Path) -> dict[str, object]:
    layout_text = '\n'.join(
        line.split('#', 1)[0].split('//', 1)[0].strip()
        for line in text.splitlines()
        if line.split('#', 1)[0].split('//', 1)[0].strip()
    ).strip()
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
        token = leaf.name.strip()
        normalized_name = token.lower()
        if normalized_name == 'cmd':
            if leaf.provider is not None:
                raise ConfigValidationError(f"{path}: reserved token 'cmd' cannot declare a provider")
            if cmd_enabled:
                raise ConfigValidationError(f'{path}: compact config cannot define cmd more than once')
            cmd_enabled = True
            continue
        if leaf.provider is None:
            raise ConfigValidationError(
                f"{path}: invalid token {token!r}; expected 'agent_name:provider' or 'cmd'"
            )
        match = _COMPACT_ENTRY_RE.fullmatch(f'{token}:{leaf.provider}')
        if match is None:
            raise ConfigValidationError(
                f"{path}: invalid token {token!r}; expected 'agent_name:provider' or 'cmd'"
            )
        if normalized_name in agents:
            raise ConfigValidationError(f'{path}: duplicate agent name in compact config: {token}')
        default_agents.append(token)
        agents[normalized_name] = _build_compact_agent_record(leaf.provider)
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


def _parse_toml_config_document(text: str, *, path: Path) -> dict[str, object]:
    try:
        if hasattr(_toml_reader, 'loads'):
            document = _toml_reader.loads(text)
        else:  # pragma: no cover
            document = _toml_reader.load(text)
    except Exception as exc:
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


def ensure_default_project_config(project_root: Path) -> Path:
    config_path = project_config_path(project_root)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        atomic_write_text(config_path, render_default_project_config_text())
    return config_path


def ensure_bootstrap_project_config(project_root: Path) -> Path:
    config_path = project_config_path(project_root)
    if config_path.exists():
        return config_path
    recovered = _recover_project_config(project_root)
    if recovered is not None:
        atomic_write_text(config_path, render_project_config_text(recovered))
        return config_path
    blockers = _persisted_anchor_state(config_path.parent)
    if blockers:
        sample = ', '.join(str(item) for item in blockers[:3])
        raise ConfigValidationError(
            f'{config_path}: missing config for existing .ccb anchor with persisted state '
            f'({sample}); restore .ccb/{CONFIG_FILENAME} or remove stale .ccb contents before reinitializing'
        )
    return ensure_default_project_config(project_root)


def _persisted_anchor_state(ccb_dir: Path) -> tuple[Path, ...]:
    if not ccb_dir.exists():
        return ()
    blockers: list[Path] = []
    for child in sorted(ccb_dir.rglob('*')):
        if child == ccb_dir:
            continue
        if child.name == CONFIG_FILENAME and child.parent == ccb_dir:
            continue
        rel = child.relative_to(ccb_dir)
        if _is_nonblocking_residue(rel):
            continue
        if child.is_symlink() or child.is_file():
            blockers.append(rel)
    return tuple(blockers)


def _recover_project_config(project_root: Path) -> ProjectConfig | None:
    layout = PathLayout(project_root)
    agents_dir = layout.agents_dir
    if not agents_dir.is_dir():
        return None
    spec_store = AgentSpecStore(layout)
    recovered_specs = {}
    for child in sorted(agents_dir.iterdir()):
        if not child.is_dir():
            continue
        try:
            spec = spec_store.load(child.name)
        except Exception:
            return None
        if spec is None:
            return None
        recovered_specs[spec.name] = spec
    if not recovered_specs:
        return None
    default_agents = tuple(sorted(recovered_specs))
    return ProjectConfig(
        version=2,
        default_agents=default_agents,
        agents=recovered_specs,
        cmd_enabled=True,
    )


def _is_nonblocking_residue(path: Path) -> bool:
    text = path.as_posix()
    name = path.name
    if len(path.parts) == 1 and name.startswith('.'):
        return True
    if text.startswith('workspaces/'):
        return True
    if text.endswith('.log') or text.endswith('.jsonl'):
        return True
    if text in {
        'ccbd/startup.lock',
        'ccbd/tmux.sock',
        'ccbd/shutdown-intent.json',
        'ccbd/startup-report.json',
        'ccbd/shutdown-report.json',
        'ccbd/restore-report.json',
        'ccbd/state.json',
        'ccbd/lease.json',
        'ccbd/tmux-cleanup-history.jsonl',
        'ccbd/lifecycle.jsonl',
        'ccbd/supervision.jsonl',
    }:
        return True
    return False


__all__ = ['ensure_bootstrap_project_config', 'ensure_default_project_config', 'load_project_config']
