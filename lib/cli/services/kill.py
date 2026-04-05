from __future__ import annotations

from dataclasses import replace

import json
import os
from pathlib import Path
import time

from agents.models import AgentState
from agents.store import AgentRuntimeStore
from ccbd.lifecycle_report_store import CcbdShutdownReportStore
from ccbd.models import CcbdRuntimeSnapshot, CcbdShutdownReport, cleanup_summaries_from_objects
from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipGuard
from ccbd.services.project_namespace import ProjectNamespaceController
from ccbd.services.start_policy import CcbdStartPolicyStore
from ccbd.system import utc_now
from ccbd.socket_client import CcbdClient
from cli.context import CliContext
from cli.kill_runtime.processes import is_pid_alive, terminate_pid_tree
from cli.models import ParsedKillCommand
from agents.config_loader import load_project_config
from ccbd.models import LeaseHealth
from terminal_runtime.tmux import normalize_socket_name, socket_name_from_tmux_env

from .daemon import CcbdServiceError, KillSummary, connect_mounted_daemon, inspect_daemon, record_shutdown_intent, shutdown_daemon
from .tmux_cleanup_history import TmuxCleanupEvent, TmuxCleanupHistoryStore
from .tmux_project_cleanup import ProjectTmuxCleanupSummary, cleanup_project_tmux_orphans_by_socket
from .tmux_ui import set_tmux_ui_active

_STOP_ALL_TIMEOUT_S = 12.0


def kill_project(context: CliContext, command: ParsedKillCommand):
    remote_summary: KillSummary | None = None
    try:
        handle = connect_mounted_daemon(context, allow_restart_stale=False)
    except CcbdServiceError:
        handle = None
    if handle is not None and handle.client is not None:
        try:
            record_shutdown_intent(context, reason='kill')
            stop_all_client = (
                CcbdClient(context.paths.ccbd_socket_path, timeout_s=_STOP_ALL_TIMEOUT_S)
                if isinstance(handle.client, CcbdClient)
                else handle.client
            )
            payload = stop_all_client.stop_all(force=command.force)
            remote_summary = _summary_from_stop_all_payload(payload)
        except Exception:
            if not command.force:
                raise
    config = load_project_config(context.project.project_root).config
    store = AgentRuntimeStore(context.paths)
    tmux_sockets = _collect_candidate_tmux_sockets()
    configured_agent_names = tuple(config.agents)
    extra_agent_names = _extra_agent_dir_names(context, configured_agent_names)
    pid_candidates: dict[int, list[Path]] = {}
    for agent_name in (*configured_agent_names, *extra_agent_names):
        runtime = store.load_best_effort(agent_name)
        if (
            runtime is not None
            and str(runtime.runtime_ref or '').startswith('tmux:')
            and getattr(runtime, 'tmux_socket_path', None) is None
        ):
            socket_name = normalize_socket_name(runtime.tmux_socket_name)
            if socket_name is not None:
                tmux_sockets.add(socket_name)
        for pid, sources in _collect_agent_pid_candidates(
            agent_dir=context.paths.agent_dir(agent_name),
            runtime=runtime,
            fallback_to_agent_dir=command.force,
        ).items():
            pid_candidates.setdefault(pid, []).extend(sources)
        if runtime is None or agent_name not in config.agents:
            continue
        store.save(
            replace(
                runtime,
                state=AgentState.STOPPED,
                pid=None,
                runtime_ref=None,
                session_ref=None,
                queue_depth=0,
                socket_path=None,
                health='stopped',
                runtime_pid=None,
                runtime_root=None,
                pane_id=None,
                active_pane_id=None,
                pane_title_marker=None,
                pane_state=None,
                tmux_socket_name=None,
                tmux_socket_path=None,
                session_file=None,
                session_id=None,
                lifecycle_state='stopped',
                desired_state='stopped',
                reconcile_state='stopped',
                last_failure_reason=None,
            )
        )
    namespace_destroy = ProjectNamespaceController(context.paths, context.project.project_id).destroy(
        reason='kill',
        force=command.force,
    )
    try:
        CcbdStartPolicyStore(context.paths).clear()
    except Exception:
        pass
    if remote_summary is not None:
        summary = _await_remote_shutdown(context, force=command.force)
    else:
        try:
            summary = shutdown_daemon(context, force=command.force)
        except CcbdServiceError:
            if not command.force:
                raise
            summary = KillSummary(
                project_id=context.project.project_id,
                state='unmounted',
                socket_path=str(context.paths.ccbd_socket_path),
                forced=command.force,
            )
    set_tmux_ui_active(False)
    cleanup_summaries = cleanup_project_tmux_orphans_by_socket(
        project_id=context.project.project_id,
        active_panes_by_socket={socket_name: () for socket_name in (tmux_sockets or {None})},
    )
    _terminate_runtime_pids(
        project_root=context.project.project_root,
        pid_candidates=pid_candidates,
    )
    if cleanup_summaries:
        TmuxCleanupHistoryStore(context.paths).append(
            TmuxCleanupEvent(
                event_kind='kill',
                project_id=context.project.project_id,
                occurred_at=utc_now(),
                summaries=cleanup_summaries,
            )
        )
    all_cleanup_summaries = _merge_cleanup_summaries(
        remote_summary.cleanup_summaries if remote_summary is not None else (),
        cleanup_summaries,
    )
    final_summary = replace(
        remote_summary or summary,
        state=summary.state,
        socket_path=summary.socket_path,
        forced=command.force,
        cleanup_summaries=all_cleanup_summaries,
    )
    _record_kill_report(
        context,
        trigger='kill' if remote_summary is not None else 'kill_fallback',
        forced=command.force,
        cleanup_summaries=all_cleanup_summaries,
    )
    return final_summary


def _await_remote_shutdown(context: CliContext, *, force: bool, timeout_s: float = 2.5) -> KillSummary:
    deadline = time.time() + max(0.1, float(timeout_s))
    last_inspection = None
    while time.time() < deadline:
        _, _, inspection = inspect_daemon(context)
        last_inspection = inspection
        if not inspection.socket_connectable and inspection.health in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED, LeaseHealth.STALE}:
            break
        time.sleep(0.05)
    lease = None if last_inspection is None else last_inspection.lease
    return KillSummary(
        project_id=context.project.project_id,
        state=lease.mount_state.value if lease is not None else 'unmounted',
        socket_path=str(context.paths.ccbd_socket_path),
        forced=force,
    )


def _summary_from_stop_all_payload(payload: dict) -> KillSummary:
    cleanup_summaries = tuple(
        ProjectTmuxCleanupSummary(
            socket_name=item.get('socket_name'),
            owned_panes=tuple(item.get('owned_panes') or ()),
            active_panes=tuple(item.get('active_panes') or ()),
            orphaned_panes=tuple(item.get('orphaned_panes') or ()),
            killed_panes=tuple(item.get('killed_panes') or ()),
        )
        for item in (payload.get('cleanup_summaries') or ())
        if isinstance(item, dict)
    )
    return KillSummary(
        project_id=str(payload.get('project_id') or ''),
        state=str(payload.get('state') or 'unmounted'),
        socket_path=str(payload.get('socket_path') or ''),
        forced=bool(payload.get('forced')),
        cleanup_summaries=cleanup_summaries,
    )


def _merge_cleanup_summaries(*groups: tuple[ProjectTmuxCleanupSummary, ...]) -> tuple[ProjectTmuxCleanupSummary, ...]:
    merged: list[ProjectTmuxCleanupSummary] = []
    for group in groups:
        merged.extend(group)
    return tuple(merged)


def _collect_candidate_tmux_sockets() -> set[str | None]:
    sockets: set[str | None] = set()
    for value in (
        normalize_socket_name(os.environ.get('CCB_TMUX_SOCKET')),
        socket_name_from_tmux_env(os.environ.get('TMUX')),
    ):
        if value is not None:
            sockets.add(value)
    return sockets or {None}


def _extra_agent_dir_names(context: CliContext, configured_agent_names: tuple[str, ...]) -> tuple[str, ...]:
    names: list[str] = []
    known = set(configured_agent_names)
    agents_dir = context.paths.agents_dir
    if agents_dir.is_dir():
        for child in sorted(agents_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name in known or child.name in names:
                continue
            names.append(child.name)
    return tuple(names)


def _collect_agent_pid_candidates(
    agent_dir: Path,
    *,
    runtime,
    fallback_to_agent_dir: bool,
) -> dict[int, list[Path]]:
    candidates: dict[int, list[Path]] = {}
    runtime_root_paths: list[Path] = []
    if runtime is not None:
        runtime_pid = _coerce_pid(getattr(runtime, 'runtime_pid', None) or getattr(runtime, 'pid', None))
        if runtime_pid is not None:
            candidates.setdefault(runtime_pid, []).append(agent_dir / 'runtime.json')
        runtime_root = getattr(runtime, 'runtime_root', None)
        if isinstance(runtime_root, str) and runtime_root.strip():
            runtime_root_paths.append(Path(runtime_root).expanduser())
    if fallback_to_agent_dir or not runtime_root_paths:
        runtime_root_paths.append(agent_dir / 'provider-runtime')
    seen_roots: set[Path] = set()
    for root in runtime_root_paths:
        try:
            resolved_root = root.resolve()
        except Exception:
            resolved_root = root.absolute()
        if resolved_root in seen_roots or not resolved_root.is_dir():
            continue
        seen_roots.add(resolved_root)
        for pid_path in sorted(resolved_root.rglob('*.pid')):
            pid = _read_pid_file(pid_path)
            if pid is None:
                continue
            candidates.setdefault(pid, []).append(pid_path)
    return candidates


def _load_runtime_pid(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return _coerce_pid(data.get('pid'))


def _read_pid_file(path: Path) -> int | None:
    try:
        return _coerce_pid(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def _coerce_pid(value: object) -> int | None:
    text = str(value or '').strip()
    if not text.isdigit():
        return None
    pid = int(text)
    return pid if pid > 0 else None


def _terminate_runtime_pids(*, project_root: Path, pid_candidates: dict[int, list[Path]]) -> None:
    for pid in sorted(pid_candidates):
        hint_paths = tuple(dict.fromkeys(pid_candidates[pid]))
        if not is_pid_alive(pid):
            _remove_pid_files(hint_paths)
            continue
        if not _pid_matches_project(pid, project_root=project_root, hint_paths=hint_paths):
            continue
        if terminate_pid_tree(pid, timeout_s=1.0, is_pid_alive_fn=is_pid_alive):
            _remove_pid_files(hint_paths)


def _record_kill_report(
    context: CliContext,
    *,
    trigger: str,
    forced: bool,
    cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...],
) -> None:
    store = CcbdShutdownReportStore(context.paths)
    runtime_store = AgentRuntimeStore(context.paths)
    manager = MountManager(context.paths)
    guard = OwnershipGuard(context.paths, manager)
    config = load_project_config(context.project.project_root).config
    snapshots = tuple(
        snapshot
        for snapshot in (
            _snapshot_for_runtime(runtime_store.load_best_effort(agent_name))
            for agent_name in (*tuple(sorted(config.agents)), *_extra_agent_dir_names(context, tuple(config.agents)))
        )
        if snapshot is not None
    )
    try:
        inspection = guard.inspect()
        store.save(
            CcbdShutdownReport(
                project_id=context.project.project_id,
                generated_at=utc_now(),
                trigger=trigger,
                status='ok',
                forced=forced,
                stopped_agents=tuple(sorted(config.agents)),
                daemon_generation=inspection.generation,
                reason='kill',
                inspection_after=inspection.to_record(),
                actions_taken=(
                    f'cleanup_tmux_orphans:killed={sum(len(item.killed_panes) for item in cleanup_summaries)}',
                    'request_shutdown_intent',
                ),
                cleanup_summaries=cleanup_summaries_from_objects(cleanup_summaries),
                runtime_snapshots=snapshots,
                failure_reason=None,
            )
        )
    except Exception:
        return


def _snapshot_for_runtime(runtime) -> CcbdRuntimeSnapshot | None:
    if runtime is None:
        return None
    try:
        return CcbdRuntimeSnapshot.from_runtime(runtime)
    except Exception:
        return None


def _pid_matches_project(pid: int, *, project_root: Path, hint_paths: tuple[Path, ...]) -> bool:
    if os.name == 'nt':
        return True

    normalized_hints: list[Path] = []
    for candidate in (project_root, *(path.parent for path in hint_paths)):
        try:
            resolved = candidate.expanduser().resolve()
        except Exception:
            resolved = candidate.expanduser().absolute()
        if resolved not in normalized_hints:
            normalized_hints.append(resolved)

    cwd_path = _read_proc_path(pid, 'cwd')
    if cwd_path is not None:
        for root in normalized_hints:
            if _path_within(cwd_path, root):
                return True

    cmdline = _read_proc_cmdline(pid)
    if cmdline:
        for candidate in (*normalized_hints, *hint_paths):
            text = str(candidate).strip()
            if text and text in cmdline:
                return True
    return False


def _read_proc_path(pid: int, entry: str) -> Path | None:
    try:
        return Path(os.readlink(f'/proc/{pid}/{entry}')).expanduser()
    except Exception:
        return None


def _read_proc_cmdline(pid: int) -> str:
    try:
        raw = Path(f'/proc/{pid}/cmdline').read_bytes()
    except Exception:
        return ''
    return raw.replace(b'\x00', b' ').decode('utf-8', errors='ignore').strip()


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except Exception:
        return False
    return True


def _remove_pid_files(paths: tuple[Path, ...]) -> None:
    for path in paths:
        if path.suffix != '.pid':
            continue
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except Exception:
            continue
