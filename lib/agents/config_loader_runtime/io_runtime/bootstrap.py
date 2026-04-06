from __future__ import annotations

from pathlib import Path

from agents.models import ProjectConfig
from agents.store import AgentSpecStore
from storage.atomic import atomic_write_text
from storage.paths import PathLayout

from ..common import CONFIG_FILENAME, ConfigValidationError
from ..defaults import render_default_project_config_text, render_project_config_text
from ..paths import project_config_path


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


__all__ = ['ensure_bootstrap_project_config', 'ensure_default_project_config']
