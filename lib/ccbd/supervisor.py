from __future__ import annotations

from pathlib import Path

from agents.config_identity import project_config_identity_payload
from ccbd.lifecycle_report_store import CcbdShutdownReportStore, CcbdStartupReportStore
from ccbd.start_flow import StartFlowSummary, run_start_flow
from ccbd.stop_flow import StopAllSummary, stop_all_project
from ccbd.system import utc_now
from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipGuard
from ccbd.services.project_namespace import ProjectNamespaceController
from ccbd.services.start_policy import CcbdStartPolicyStore
from ccbd.supervisor_runtime import start_supervisor, stop_all_supervisor
from cli.services.tmux_cleanup_history import TmuxCleanupHistoryStore
from cli.services.tmux_project_cleanup import cleanup_project_tmux_orphans_by_socket


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
        return start_supervisor(
            self,
            agent_names=agent_names,
            restore=restore,
            auto_permission=auto_permission,
            cleanup_tmux_orphans=cleanup_tmux_orphans,
            interactive_tmux_layout=interactive_tmux_layout,
            recreate_namespace=recreate_namespace,
            recreate_reason=recreate_reason,
            run_start_flow_fn=run_start_flow,
        )

    def stop_all(self, *, force: bool) -> StopAllSummary:
        return stop_all_supervisor(
            self,
            force=force,
            cleanup_project_tmux_orphans_by_socket_fn=cleanup_project_tmux_orphans_by_socket,
            tmux_cleanup_history_store_cls=TmuxCleanupHistoryStore,
            stop_all_project_fn=stop_all_project,
        )


__all__ = ['RuntimeSupervisor', 'StopAllSummary']
