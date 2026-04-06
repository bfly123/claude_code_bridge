from __future__ import annotations

from dataclasses import replace

from agents.models import AgentState, RuntimeMode
from ccbd.services.runtime_recovery_policy import normalized_runtime_health, should_attempt_background_recovery
from ccbd.system import parse_utc_timestamp, utc_now
from ccbd.supervision.backoff import backoff_delay_seconds as backoff_delay_seconds_impl
from ccbd.supervision.backoff import is_in_backoff_window as is_in_backoff_window_impl
from ccbd.supervision.backoff import same_socket_path as same_socket_path_impl
from ccbd.supervision.mount import build_starting_runtime as build_starting_runtime_impl
from ccbd.supervision.mount import ensure_mounted as ensure_mounted_impl
from ccbd.supervision.mount import persist_mount_failure as persist_mount_failure_impl
from ccbd.supervision.recovery import recover_runtime as recover_runtime_impl

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
        clock=utc_now,
        generation_getter=None,
        event_store: SupervisionEventStore | None = None,
    ) -> None:
        self._project_id = project_id
        self._layout = layout
        self._config = config
        self._registry = registry
        self._runtime_service = runtime_service
        self._mount_agent_fn = mount_agent_fn
        self._remount_project_fn = remount_project_fn
        self._clock = clock
        self._generation_getter = generation_getter or (lambda: None)
        self._event_store = event_store or SupervisionEventStore(layout)

    def reconcile_once(self) -> dict[str, str]:
        statuses: dict[str, str] = {}
        for agent_name in self._config.agents:
            statuses[agent_name] = self._reconcile_agent(agent_name)
        return statuses

    def _reconcile_agent(self, agent_name: str) -> str:
        runtime = self._resolved_runtime(agent_name)
        if runtime is None:
            return self._ensure_mounted(agent_name, runtime=None)
        if self._runtime_requires_mount(runtime):
            return self._ensure_mounted(agent_name, runtime=runtime)
        if self._runtime_requires_mount_from_foreign_pane(runtime):
            return self._ensure_mounted(agent_name, runtime=runtime)
        if not self._runtime_requires_recovery(runtime):
            return runtime.health
        return self._recover_runtime(agent_name, runtime=runtime)

    def _ensure_mounted(self, agent_name: str, *, runtime):
        return ensure_mounted_impl(
            project_id=self._project_id,
            agent_name=agent_name,
            runtime=runtime,
            registry=self._registry,
            runtime_service=self._runtime_service,
            mount_agent_fn=self._mount_agent_fn,
            remount_project_fn=self._remount_project_fn,
            clock=self._clock,
            event_store=self._event_store,
            upsert_if_changed_fn=self._upsert_if_changed,
            build_starting_runtime_fn=self._build_starting_runtime,
            persist_mount_failure_fn=self._persist_mount_failure,
            is_in_backoff_window_fn=self._is_in_backoff_window,
            should_reflow_project_mount_fn=self._should_reflow_project_mount,
            align_runtime_authority_fn=self._align_runtime_authority,
            normalized_runtime_health_fn=normalized_runtime_health,
        )

    def _persist_mount_failure(
        self,
        runtime,
        *,
        agent_name: str,
        attempted_at: str,
        prior_health: str,
        next_restart_count: int,
        reason: str,
    ) -> str:
        return persist_mount_failure_impl(
            runtime,
            project_id=self._project_id,
            agent_name=agent_name,
            attempted_at=attempted_at,
            prior_health=prior_health,
            next_restart_count=next_restart_count,
            reason=reason,
            event_store=self._event_store,
            upsert_if_changed_fn=self._upsert_if_changed,
        )

    def _align_runtime_authority(self, runtime):
        next_generation = self._generation_getter()
        daemon_generation = runtime.daemon_generation if next_generation is None else next_generation
        desired_state = 'stopped' if runtime.state is AgentState.STOPPED else 'mounted'
        reconcile_state = self._resolved_reconcile_state(runtime)
        return self._upsert_if_changed(
            runtime,
            daemon_generation=daemon_generation,
            desired_state=desired_state,
            reconcile_state=reconcile_state,
        )

    def _upsert_if_changed(self, runtime, **updates):
        candidate = replace(runtime, **updates)
        if candidate == runtime:
            return runtime
        return self._registry.upsert(candidate)

    def _build_starting_runtime(self, agent_name: str, *, runtime, attempted_at: str):
        return build_starting_runtime_impl(
            agent_name,
            runtime=runtime,
            attempted_at=attempted_at,
            layout=self._layout,
            registry=self._registry,
            runtime_service=self._runtime_service,
            generation_getter=self._generation_getter,
        )

    def _is_in_backoff_window(self, runtime, *, now: str) -> bool:
        return is_in_backoff_window_impl(
            runtime,
            now=now,
            parse_utc_timestamp_fn=parse_utc_timestamp,
            backoff_delay_seconds_fn=_backoff_delay_seconds,
        )

    def _should_reflow_project_namespace(self, runtime) -> bool:
        if not self._runtime_in_project_namespace_reflow_health(runtime):
            return False
        if not self._project_namespace_reflow_safe(runtime.agent_name):
            return False
        socket_path = str(getattr(runtime, 'tmux_socket_path', None) or '').strip()
        if not socket_path:
            return False
        if not _same_socket_path(socket_path, str(self._layout.ccbd_tmux_socket_path)):
            return False
        return True

    def _should_reflow_project_mount(self, agent_name: str) -> bool:
        if not bool(getattr(self._config, 'cmd_enabled', False)):
            return False
        return self._project_namespace_reflow_safe(agent_name)

    def _project_namespace_reflow_safe(self, agent_name: str) -> bool:
        if self._remount_project_fn is None:
            return False
        spec = self._runtime_mode_spec(agent_name)
        if spec is None:
            return False
        if getattr(spec, 'runtime_mode', None) is not RuntimeMode.PANE_BACKED:
            return False
        return not self._other_project_agent_busy(agent_name)

    def _recover_runtime(self, agent_name: str, *, runtime) -> str:
        return recover_runtime_impl(
            project_id=self._project_id,
            agent_name=agent_name,
            runtime=runtime,
            registry=self._registry,
            runtime_service=self._runtime_service,
            remount_project_fn=self._remount_project_fn,
            clock=self._clock,
            event_store=self._event_store,
            align_runtime_authority_fn=self._align_runtime_authority,
            upsert_if_changed_fn=self._upsert_if_changed,
            is_in_backoff_window_fn=self._is_in_backoff_window,
            should_reflow_project_namespace_fn=self._should_reflow_project_namespace,
        )

    def _resolved_runtime(self, agent_name: str):
        runtime = self._registry.get(agent_name)
        if runtime is None:
            return None
        return self._align_runtime_authority(runtime)

    def _runtime_requires_mount(self, runtime) -> bool:
        return runtime.state in {AgentState.STOPPED, AgentState.FAILED}

    def _runtime_requires_mount_from_foreign_pane(self, runtime) -> bool:
        return self._runtime_health(runtime) == 'pane-foreign' and not self._should_reflow_project_namespace(runtime)

    def _runtime_requires_recovery(self, runtime) -> bool:
        return self._should_reflow_project_namespace(runtime) or should_attempt_background_recovery(runtime)

    def _runtime_health(self, runtime) -> str:
        return normalized_runtime_health(runtime)

    def _resolved_reconcile_state(self, runtime) -> str | None:
        reconcile_state = runtime.reconcile_state
        if runtime.state is AgentState.STOPPED:
            return 'stopped'
        if runtime.state is AgentState.FAILED:
            return 'failed'
        if runtime.state is AgentState.DEGRADED and reconcile_state == 'steady':
            return 'degraded'
        if runtime.state in {AgentState.STARTING, AgentState.IDLE, AgentState.BUSY}:
            if reconcile_state in {None, '', 'degraded', 'recovering', 'failed', 'stopped'}:
                return 'steady'
        return reconcile_state

    def _runtime_in_project_namespace_reflow_health(self, runtime) -> bool:
        return self._runtime_health(runtime) in {'pane-dead', 'pane-missing', 'pane-foreign'}

    def _runtime_mode_spec(self, agent_name: str):
        try:
            return self._registry.spec_for(agent_name)
        except Exception:
            return None

    def _other_project_agent_busy(self, agent_name: str) -> bool:
        for other_name in self._config.agents:
            other = self._registry.get(other_name)
            if other is None or other.agent_name == agent_name:
                continue
            if other.state is AgentState.BUSY:
                return True
        return False


def _backoff_delay_seconds(restart_count: int) -> int:
    return backoff_delay_seconds_impl(restart_count)


def _same_socket_path(left: str, right: str) -> bool:
    return same_socket_path_impl(left, right)


__all__ = ['RuntimeSupervisionLoop']
