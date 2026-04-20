from __future__ import annotations

import json
from pathlib import Path

_TAIL_SUFFIXES = {'.log', '.jsonl', '.txt', '.yaml', '.yml'}
_COPY_SUFFIXES = {'.json', '.pid'}
_PROVIDER_STATE_SUFFIXES = _TAIL_SUFFIXES | _COPY_SUFFIXES | {'.toml'}
_PROVIDER_STATE_SECRET_FILENAMES = {'auth.json'}


def project_root_sources(context) -> tuple[tuple[str, Path], ...]:
    items: list[tuple[str, Path]] = [
        ('project-config', context.paths.config_path),
        ('ccbd-authority', context.paths.ccbd_lease_path),
        ('ccbd-authority', context.paths.ccbd_keeper_path),
        ('ccbd-authority', context.paths.ccbd_shutdown_intent_path),
        ('ccbd-authority', context.paths.ccbd_state_path),
        ('ccbd-authority', context.paths.ccbd_start_policy_path),
        ('ccbd-report', context.paths.ccbd_startup_report_path),
        ('ccbd-report', context.paths.ccbd_shutdown_report_path),
        ('ccbd-report', context.paths.ccbd_restore_report_path),
        ('ccbd-events', context.paths.ccbd_submissions_path),
        ('ccbd-events', context.paths.ccbd_messages_path),
        ('ccbd-events', context.paths.ccbd_attempts_path),
        ('ccbd-events', context.paths.ccbd_replies_path),
        ('ccbd-events', context.paths.ccbd_dead_letters_path),
        ('ccbd-events', context.paths.ccbd_supervision_path),
        ('ccbd-events', context.paths.ccbd_lifecycle_log_path),
        ('ccbd-events', context.paths.ccbd_tmux_cleanup_history_path),
        ('ccbd-log', context.paths.ccbd_dir / 'ccbd.stdout.log'),
        ('ccbd-log', context.paths.ccbd_dir / 'ccbd.stderr.log'),
        ('ccbd-log', context.paths.ccbd_dir / 'keeper.stdout.log'),
        ('ccbd-log', context.paths.ccbd_dir / 'keeper.stderr.log'),
    ]

    items.extend(iter_dir_files('ccbd-execution', context.paths.ccbd_executions_dir, suffixes={'.json'}))
    items.extend(iter_dir_files('ccbd-snapshot', context.paths.ccbd_snapshots_dir, suffixes={'.json'}))
    items.extend(iter_dir_files('ccbd-cursor', context.paths.ccbd_cursors_dir, suffixes={'.json'}))
    items.extend(iter_dir_files('ccbd-heartbeat', context.paths.ccbd_heartbeats_dir, suffixes={'.json'}))
    items.extend(iter_dir_files('ccbd-health', context.paths.ccbd_provider_health_dir, suffixes={'.jsonl'}))
    items.extend(iter_dir_files('ccbd-mailbox', context.paths.ccbd_mailboxes_dir, suffixes={'.json', '.jsonl'}))
    items.extend(iter_dir_files('ccbd-lease', context.paths.ccbd_leases_dir, suffixes={'.json'}))
    items.extend(_agent_source_items(context, seen_sources={path for _, path in items}))
    return tuple(items)


def iter_dir_files(category: str, root: Path, *, suffixes: set[str]) -> list[tuple[str, Path]]:
    if not root.exists() or not root.is_dir():
        return []
    files: list[tuple[str, Path]] = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        files.append((category, path))
    return files


def iter_provider_state_files(category: str, root: Path) -> list[tuple[str, Path]]:
    if not root.exists() or not root.is_dir():
        return []
    files: list[tuple[str, Path]] = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in _PROVIDER_STATE_SUFFIXES:
            continue
        if path.name.lower() in _PROVIDER_STATE_SECRET_FILENAMES:
            continue
        files.append((category, path))
    return files


def iter_agent_dirs(context) -> tuple[Path, ...]:
    root = context.paths.agents_dir
    if not root.exists() or not root.is_dir():
        return ()
    return tuple(path for path in sorted(root.iterdir()) if path.is_dir())


def session_path_from_runtime(runtime_path: Path) -> Path | None:
    try:
        payload = json.loads(runtime_path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    for key in ('session_file', 'session_ref'):
        candidate = payload.get(key)
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        path = Path(candidate).expanduser()
        if path.is_absolute() and path.exists():
            return path
    return None


def archive_path_for_source(context, source: Path) -> str:
    try:
        relative = source.resolve().relative_to(context.project.project_root.resolve())
        return str(Path('project') / relative)
    except Exception:
        safe_parts = [part for part in source.parts if part not in ('/', '')]
        return str(Path('external') / Path(*safe_parts[-4:]))


def _agent_source_items(context, *, seen_sources: set[Path]) -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for agent_dir in iter_agent_dirs(context):
        agent_name = agent_dir.name
        for category, path in _agent_sources(context, agent_name, agent_dir):
            resolved = _resolve_source(path)
            if resolved in seen_sources:
                continue
            seen_sources.add(resolved)
            items.append((category, path))
    return items


def _resolve_source(path: Path) -> Path:
    try:
        return path.resolve()
    except Exception:
        return path.absolute()


def _agent_sources(context, agent_name: str, agent_dir: Path) -> tuple[tuple[str, Path], ...]:
    items: list[tuple[str, Path]] = [
        ('agent-authority', context.paths.agent_spec_path(agent_name)),
        ('agent-authority', context.paths.agent_runtime_path(agent_name)),
        ('agent-authority', context.paths.agent_restore_path(agent_name)),
        ('agent-events', context.paths.agent_jobs_path(agent_name)),
        ('agent-events', context.paths.agent_events_path(agent_name)),
        ('agent-workspace', context.paths.workspace_binding_path(agent_name)),
    ]
    items.extend(iter_dir_files('agent-log', context.paths.agent_logs_dir(agent_name), suffixes=_TAIL_SUFFIXES))
    items.extend(iter_dir_files('agent-runtime', agent_dir / 'provider-runtime', suffixes=_TAIL_SUFFIXES | _COPY_SUFFIXES))
    items.extend(iter_provider_state_files('agent-provider-state', agent_dir / 'provider-state'))

    runtime_path = context.paths.agent_runtime_path(agent_name)
    if runtime_path.exists():
        session_path = session_path_from_runtime(runtime_path)
        if session_path is not None:
            items.append(('agent-session', session_path))
    return tuple(items)


__all__ = ['archive_path_for_source', 'iter_dir_files', 'project_root_sources', 'session_path_from_runtime']
