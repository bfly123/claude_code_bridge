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
from ccbd.supervisor_runtime.state_bundle import SupervisorRuntimeState, SupervisorRuntimeStateMixin
from cli.services.tmux_cleanup_history import TmuxCleanupHistoryStore
from cli.services.tmux_project_cleanup import cleanup_project_tmux_orphans_by_socket


class RuntimeSupervisor(SupervisorRuntimeStateMixin):
    def __init__(self, *, project_root: Path, project_id: str, paths, config, registry, runtime_service, project_namespace: ProjectNamespaceController | None = None, clock=utc_now) -> None:
        mount_manager = MountManager(paths, clock=clock)
        self._runtime_state = SupervisorRuntimeState(
            project_root=Path(project_root).expanduser().resolve(),
            project_id=project_id,
            paths=paths,
            config=config,
            config_identity=project_config_identity_payload(config),
            registry=registry,
            runtime_service=runtime_service,
            project_namespace=project_namespace,
            clock=clock,
            mount_manager=mount_manager,
            ownership_guard=OwnershipGuard(paths, mount_manager, clock=clock),
            startup_report_store=CcbdStartupReportStore(paths),
            shutdown_report_store=CcbdShutdownReportStore(paths),
            start_policy_store=CcbdStartPolicyStore(paths),
        )

    def start(
        self,
        *,
        agent_names: tuple[str, ...],
        restore: bool,
        auto_permission: bool,
        cleanup_tmux_orphans: bool = True,
        interactive_tmux_layout: bool = True,
        recreate_namespace: bool = False,
        reflow_workspace: bool = False,
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
            reflow_workspace=reflow_workspace,
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
