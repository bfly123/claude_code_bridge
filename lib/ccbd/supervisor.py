from __future__ import annotations

from dataclasses import dataclass, replace
import inspect
import os
from pathlib import Path

from agents.models import AgentState
from agents.models import build_project_layout_plan
from agents.store import AgentRuntimeStore
from agents.config_identity import project_config_identity_payload
from ccbd.lifecycle_report_store import CcbdShutdownReportStore, CcbdStartupReportStore
from ccbd.models import (
    CcbdRuntimeSnapshot,
    CcbdShutdownReport,
    CcbdStartupReport,
    cleanup_summaries_from_objects,
)
from ccbd.start_flow import StartFlowSummary, run_start_flow
from ccbd.system import utc_now
from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipGuard
from ccbd.services.project_namespace import ProjectNamespaceController
from ccbd.services.start_policy import CcbdStartPolicyStore
from cli.kill_runtime.processes import is_pid_alive, terminate_pid_tree
from cli.services.tmux_cleanup_history import TmuxCleanupEvent, TmuxCleanupHistoryStore
from cli.services.tmux_project_cleanup import ProjectTmuxCleanupSummary, cleanup_project_tmux_orphans_by_socket
from terminal_runtime.tmux import normalize_socket_name


@dataclass(frozen=True)
class StopAllSummary:
    project_id: str
    state: str
    socket_path: str
    forced: bool
    stopped_agents: tuple[str, ...] = ()
    cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            'project_id': self.project_id,
            'state': self.state,
            'socket_path': self.socket_path,
            'forced': self.forced,
            'stopped_agents': list(self.stopped_agents),
            'cleanup_summaries': [
                {
                    'socket_name': item.socket_name,
                    'owned_panes': list(item.owned_panes),
                    'active_panes': list(item.active_panes),
                    'orphaned_panes': list(item.orphaned_panes),
                    'killed_panes': list(item.killed_panes),
                }
                for item in self.cleanup_summaries
            ],
        }


class RuntimeSupervisor:
    def __init__(self, *, project_root: Path, project_id: str, paths, config, registry, runtime_service, project_namespace: ProjectNamespaceController | None = None, clock=utc_now) -> None:
        self._project_root = Path(project_root).expanduser().resolve()
        self._project_id = project_id
        self._paths = paths
        self._config = config
        self._config_identity = project_config_identity_payload(config)
        self._registry = registry
        self._runtime_service = runtime_service
        self._project_namespace = project_namespace
        self._clock = clock
        self._mount_manager = MountManager(paths, clock=clock)
        self._ownership_guard = OwnershipGuard(paths, self._mount_manager, clock=clock)
        self._startup_report_store = CcbdStartupReportStore(paths)
        self._shutdown_report_store = CcbdShutdownReportStore(paths)
        self._start_policy_store = CcbdStartPolicyStore(paths)

    def start(
        self,
        *,
        agent_names: tuple[str, ...],
        restore: bool,
        auto_permission: bool,
        cleanup_tmux_orphans: bool = True,
        interactive_tmux_layout: bool = True,
        recreate_namespace: bool = False,
        recreate_reason: str | None = None,
    ) -> StartFlowSummary:
        try:
            namespace_layout_signature = (
                build_project_layout_plan(self._config, requested_agents=agent_names).signature
                if self._project_namespace is not None and interactive_tmux_layout
                else None
            )
            namespace = (
                _ensure_project_namespace(
                    self._project_namespace,
                    layout_signature=namespace_layout_signature,
                    recreate_namespace=recreate_namespace,
                    recreate_reason=recreate_reason,
                )
                if self._project_namespace is not None
                else None
            )
            summary = run_start_flow(
                project_root=self._project_root,
                project_id=self._project_id,
                paths=self._paths,
                config=self._config,
                runtime_service=self._runtime_service,
                requested_agents=agent_names,
                restore=restore,
                auto_permission=auto_permission,
                cleanup_tmux_orphans=cleanup_tmux_orphans,
                interactive_tmux_layout=interactive_tmux_layout,
                tmux_socket_path=namespace.tmux_socket_path if namespace is not None else None,
                tmux_session_name=namespace.tmux_session_name if namespace is not None else None,
                namespace_epoch=namespace.namespace_epoch if namespace is not None else None,
                fresh_namespace=bool(getattr(namespace, 'created_this_call', False)),
                clock=self._clock,
            )
        except Exception as exc:
            self._record_startup_report(
                requested_agents=agent_names,
                restore=restore,
                auto_permission=auto_permission,
                status='failed',
                actions_taken=('start_flow_failed',),
                cleanup_summaries=(),
                agent_results=(),
                failure_reason=str(exc),
            )
            raise
        self._record_startup_report(
            requested_agents=agent_names,
            restore=restore,
            auto_permission=auto_permission,
            status='ok',
            actions_taken=summary.actions_taken,
            cleanup_summaries=summary.cleanup_summaries,
            agent_results=summary.agent_results,
            failure_reason=None,
        )
        return summary

    def stop_all(self, *, force: bool) -> StopAllSummary:
        tmux_sockets: set[str | None] = set()
        pid_candidates: dict[int, list[Path]] = {}
        stopped_agents: list[str] = []
        runtime_store = AgentRuntimeStore(self._paths)
        configured_agent_names = tuple(self._registry.list_known_agents())
        extra_agent_names = _extra_agent_dir_names(self._paths, configured_agent_names)
        cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...] = ()
        actions_taken: list[str] = []
        try:
            if self._project_namespace is not None:
                namespace_destroy = self._project_namespace.destroy(reason='stop_all', force=force)
                actions_taken.append(
                    'destroy_namespace:'
                    f'destroyed={str(namespace_destroy.destroyed).lower()}'
                    f',epoch={namespace_destroy.namespace_epoch}'
                )
            for agent_name in (*configured_agent_names, *extra_agent_names):
                runtime = _best_effort_runtime(
                    agent_name=agent_name,
                    configured_agent_names=configured_agent_names,
                    registry=self._registry,
                    runtime_store=runtime_store,
                )
                if (
                    runtime is not None
                    and str(runtime.runtime_ref or '').startswith('tmux:')
                    and getattr(runtime, 'tmux_socket_path', None) is None
                ):
                    socket_name = normalize_socket_name(runtime.tmux_socket_name)
                    if socket_name is not None:
                        tmux_sockets.add(socket_name)
                for pid, sources in _collect_pid_candidates(
                    self._paths.agent_dir(agent_name),
                    runtime=runtime,
                    fallback_to_agent_dir=force,
                ).items():
                    pid_candidates.setdefault(pid, []).extend(sources)
                if runtime is None or agent_name not in configured_agent_names:
                    continue
                self._registry.upsert(
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
                stopped_agents.append(agent_name)
                actions_taken.append(f'mark_runtime_stopped:{agent_name}')

            if tmux_sockets:
                cleanup_summaries = cleanup_project_tmux_orphans_by_socket(
                    project_id=self._project_id,
                    active_panes_by_socket={socket_name: () for socket_name in tmux_sockets},
                )
                total_killed = sum(len(item.killed_panes) for item in cleanup_summaries)
                actions_taken.append(f'cleanup_tmux_orphans:killed={total_killed}')
                TmuxCleanupHistoryStore(self._paths).append(
                    TmuxCleanupEvent(
                        event_kind='kill',
                        project_id=self._project_id,
                        occurred_at=self._clock(),
                        summaries=cleanup_summaries,
                    )
                )
            else:
                actions_taken.append('cleanup_tmux_orphans:skipped')
            _terminate_runtime_pids(project_root=self._project_root, pid_candidates=pid_candidates)
            actions_taken.append(f'terminate_runtime_pids:{len(pid_candidates)}')
            summary = StopAllSummary(
                project_id=self._project_id,
                state='unmounted',
                socket_path=str(self._paths.ccbd_socket_path),
                forced=force,
                stopped_agents=tuple(stopped_agents),
                cleanup_summaries=cleanup_summaries,
            )
        except Exception as exc:
            self._record_shutdown_report(
                trigger='stop_all',
                status='failed',
                forced=force,
                reason='stop_all',
                stopped_agents=tuple(stopped_agents),
                actions_taken=tuple(actions_taken) + ('stop_all_failed',),
                cleanup_summaries=cleanup_summaries,
                failure_reason=str(exc),
            )
            raise

        self._record_shutdown_report(
            trigger='stop_all',
            status='ok',
            forced=force,
            reason='stop_all',
            stopped_agents=tuple(stopped_agents),
            actions_taken=tuple(actions_taken),
            cleanup_summaries=cleanup_summaries,
            failure_reason=None,
        )
        try:
            self._start_policy_store.clear()
        except Exception:
            pass
        return summary

    def _record_startup_report(
        self,
        *,
        requested_agents: tuple[str, ...],
        restore: bool,
        auto_permission: bool,
        status: str,
        actions_taken: tuple[str, ...],
        cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...],
        agent_results,
        failure_reason: str | None,
    ) -> None:
        try:
            inspection = self._ownership_guard.inspect()
            report = CcbdStartupReport(
                project_id=self._project_id,
                generated_at=self._clock(),
                trigger='start_command',
                status=status,
                requested_agents=tuple(requested_agents),
                desired_agents=tuple(sorted(self._config.agents)),
                restore_requested=restore,
                auto_permission=auto_permission,
                daemon_generation=inspection.generation,
                daemon_started=None,
                config_signature=str(self._config_identity.get('config_signature') or '').strip() or None,
                inspection=inspection.to_record(),
                restore_summary={},
                actions_taken=tuple(actions_taken),
                cleanup_summaries=cleanup_summaries_from_objects(cleanup_summaries),
                agent_results=tuple(agent_results),
                failure_reason=failure_reason,
            )
            self._startup_report_store.save(report)
        except Exception:
            return

    def _record_shutdown_report(
        self,
        *,
        trigger: str,
        status: str,
        forced: bool,
        reason: str,
        stopped_agents: tuple[str, ...],
        actions_taken: tuple[str, ...],
        cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...],
        failure_reason: str | None,
    ) -> None:
        try:
            inspection = self._ownership_guard.inspect()
            runtime_snapshots = tuple(
                snapshot
                for snapshot in (
                    _snapshot_for_runtime(AgentRuntimeStore(self._paths).load_best_effort(agent_name))
                    for agent_name in (*tuple(sorted(self._config.agents)), *_extra_agent_dir_names(self._paths, tuple(self._registry.list_known_agents())))
                )
                if snapshot is not None
            )
            report = CcbdShutdownReport(
                project_id=self._project_id,
                generated_at=self._clock(),
                trigger=trigger,
                status=status,
                forced=forced,
                stopped_agents=stopped_agents,
                daemon_generation=inspection.generation,
                reason=reason,
                inspection_after=inspection.to_record(),
                actions_taken=actions_taken,
                cleanup_summaries=cleanup_summaries_from_objects(cleanup_summaries),
                runtime_snapshots=runtime_snapshots,
                failure_reason=failure_reason,
            )
            self._shutdown_report_store.save(report)
        except Exception:
            return


def _ensure_project_namespace(
    project_namespace,
    *,
    layout_signature: str | None,
    recreate_namespace: bool,
    recreate_reason: str | None,
):
    ensure_fn = project_namespace.ensure
    if not recreate_namespace and not str(recreate_reason or '').strip() and not str(layout_signature or '').strip():
        return ensure_fn()
    kwargs = {
        'layout_signature': layout_signature,
        'force_recreate': recreate_namespace,
        'recreate_reason': recreate_reason,
    }
    try:
        signature = inspect.signature(ensure_fn)
    except (TypeError, ValueError):
        signature = None
    if signature is not None:
        parameters = signature.parameters
        supports_kwargs = any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
        if supports_kwargs or {'layout_signature', 'force_recreate', 'recreate_reason'} <= set(parameters):
            return ensure_fn(**kwargs)
        return ensure_fn()
    try:
        return ensure_fn(**kwargs)
    except TypeError:
        return ensure_fn()


def _best_effort_runtime(*, agent_name: str, configured_agent_names: tuple[str, ...], registry, runtime_store: AgentRuntimeStore):
    if agent_name in configured_agent_names:
        try:
            return registry.get(agent_name)
        except Exception:
            return runtime_store.load_best_effort(agent_name)
    return runtime_store.load_best_effort(agent_name)


def _snapshot_for_runtime(runtime) -> CcbdRuntimeSnapshot | None:
    if runtime is None:
        return None
    try:
        return CcbdRuntimeSnapshot.from_runtime(runtime)
    except Exception:
        return None


def _extra_agent_dir_names(paths, configured_agent_names: tuple[str, ...]) -> tuple[str, ...]:
    names: list[str] = []
    known = set(configured_agent_names)
    agents_dir = paths.agents_dir
    if agents_dir.is_dir():
        for child in sorted(agents_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name in known or child.name in names:
                continue
            names.append(child.name)
    return tuple(names)


def _collect_pid_candidates(agent_dir: Path, *, runtime, fallback_to_agent_dir: bool) -> dict[int, list[Path]]:
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


__all__ = ['RuntimeSupervisor', 'StopAllSummary']
