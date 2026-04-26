from __future__ import annotations

from ccbd.system import utc_now

from .cmd_slot import reconcile_cmd_slot
from .loop_actions import ensure_agent_mounted, recover_agent_runtime
from .loop_context import build_runtime_supervision_context
from .loop_runtime import (
    resolved_runtime,
    runtime_requires_mount,
    runtime_requires_mount_from_foreign_pane,
    runtime_requires_recovery,
    should_shutdown_for_exited_pane,
)
from .store import SupervisionEvent, SupervisionEventStore


class RuntimeSupervisionLoop:
    def __init__(
        self,
        *,
        project_id: str,
        layout,
        config,
        registry,
        runtime_service,
        mount_agent_fn=None,
        remount_project_fn=None,
        shutdown_project_fn=None,
        clock=utc_now,
        generation_getter=None,
        event_store: SupervisionEventStore | None = None,
    ) -> None:
        self._ctx = build_runtime_supervision_context(
            project_id=project_id,
            layout=layout,
            config=config,
            registry=registry,
            runtime_service=runtime_service,
            mount_agent_fn=mount_agent_fn,
            remount_project_fn=remount_project_fn,
            shutdown_project_fn=shutdown_project_fn,
            clock=clock,
            generation_getter=generation_getter,
            event_store=event_store,
        )

    def reconcile_once(self) -> dict[str, str]:
        cmd_status = reconcile_cmd_slot(self._ctx)
        if cmd_status == 'pane-exited':
            self._request_project_shutdown('pane_exited:cmd')
            return {agent_name: 'shutdown-requested' for agent_name in self._ctx.config.agents}
        statuses: dict[str, str] = {}
        for agent_name in self._ctx.config.agents:
            runtime = resolved_runtime(self._ctx, agent_name)
            if runtime is not None and should_shutdown_for_exited_pane(self._ctx, runtime):
                self._request_project_shutdown(f'pane_exited:{agent_name}')
                return {name: 'shutdown-requested' for name in self._ctx.config.agents}
            statuses[agent_name] = self._reconcile_agent(agent_name, runtime=runtime)
        return statuses

    def _reconcile_agent(self, agent_name: str, *, runtime=None) -> str:
        runtime = resolved_runtime(self._ctx, agent_name) if runtime is None else runtime
        if runtime is None:
            return ensure_agent_mounted(self._ctx, agent_name, runtime=None)
        if runtime_requires_mount(runtime):
            return ensure_agent_mounted(self._ctx, agent_name, runtime=runtime)
        if runtime_requires_mount_from_foreign_pane(self._ctx, runtime):
            return ensure_agent_mounted(self._ctx, agent_name, runtime=runtime)
        if not runtime_requires_recovery(self._ctx, runtime):
            return runtime.health
        return recover_agent_runtime(self._ctx, agent_name, runtime=runtime)

    def _request_project_shutdown(self, reason: str) -> None:
        self._ctx.event_store.append(
            SupervisionEvent(
                event_kind='shutdown_requested',
                project_id=self._ctx.project_id,
                agent_name=reason.partition(':')[2] or 'project',
                occurred_at=self._ctx.clock(),
                daemon_generation=self._ctx.generation_getter(),
                details={'reason': reason},
            )
        )
        if self._ctx.shutdown_project_fn is not None:
            self._ctx.shutdown_project_fn(reason)


__all__ = ['RuntimeSupervisionLoop']
