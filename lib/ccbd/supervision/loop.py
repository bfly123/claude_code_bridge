from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from agents.models import AgentState, RuntimeMode
from ccbd.services.runtime_recovery_policy import normalized_runtime_health, should_attempt_background_recovery
from ccbd.system import parse_utc_timestamp, utc_now

from .store import SupervisionEvent, SupervisionEventStore

_SUCCESS_RUNTIME_HEALTHS = frozenset({'healthy', 'restored'})


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
        runtime = self._registry.get(agent_name)
        if runtime is None:
            return self._ensure_mounted(agent_name, runtime=None)
        runtime = self._align_runtime_authority(runtime)
        if runtime.state in {AgentState.STOPPED, AgentState.FAILED}:
            return self._ensure_mounted(agent_name, runtime=runtime)
        foreign_namespace_reflow = (
            normalized_runtime_health(runtime) == 'pane-foreign'
            and self._should_reflow_project_namespace(runtime)
        )
        if normalized_runtime_health(runtime) == 'pane-foreign' and not foreign_namespace_reflow:
            return self._ensure_mounted(agent_name, runtime=runtime)
        if not foreign_namespace_reflow and not should_attempt_background_recovery(runtime):
            return runtime.health
        attempted_at = self._clock()
        if self._is_in_backoff_window(runtime, now=attempted_at):
            return runtime.health
        prior_health = normalized_runtime_health(runtime) or runtime.health
        recovering = self._upsert_if_changed(
            runtime,
            reconcile_state='recovering',
            last_reconcile_at=attempted_at,
            lifecycle_state='recovering',
        )
        self._event_store.append(
            SupervisionEvent(
                event_kind='recover_started',
                project_id=self._project_id,
                agent_name=agent_name,
                occurred_at=attempted_at,
                daemon_generation=recovering.daemon_generation,
                desired_state=recovering.desired_state,
                reconcile_state=recovering.reconcile_state,
                prior_health=prior_health,
                result_health=prior_health,
                runtime_state=recovering.state.value,
                runtime_ref=recovering.runtime_ref,
                session_ref=recovering.session_ref,
            )
        )
        restart_count = recovering.restart_count + 1

        try:
            if self._should_reflow_project_namespace(recovering):
                self._remount_project_fn(f'pane_recovery:{agent_name}')
                refreshed = self._registry.get(agent_name)
            else:
                refreshed = self._runtime_service.refresh_provider_binding(agent_name, recover=True)
            failure_reason = None
        except Exception as exc:
            refreshed = self._registry.get(agent_name) or recovering
            failure_reason = f'{type(exc).__name__}: {exc}'

        if refreshed is None:
            failed = self._upsert_if_changed(
                recovering,
                reconcile_state='degraded',
                restart_count=restart_count,
                last_reconcile_at=attempted_at,
                last_failure_reason='runtime-missing-after-recover',
                lifecycle_state='degraded',
            )
            self._event_store.append(
                SupervisionEvent(
                    event_kind='recover_failed',
                    project_id=self._project_id,
                    agent_name=agent_name,
                    occurred_at=attempted_at,
                    daemon_generation=failed.daemon_generation,
                    desired_state=failed.desired_state,
                    reconcile_state=failed.reconcile_state,
                    prior_health=prior_health,
                    result_health='unmounted',
                    runtime_state=failed.state.value,
                    runtime_ref=failed.runtime_ref,
                    session_ref=failed.session_ref,
                    details={'reason': 'runtime-missing-after-recover'},
                )
            )
            return 'unmounted'

        refreshed = self._align_runtime_authority(refreshed)
        next_health = normalized_runtime_health(refreshed) or refreshed.health
        if next_health in _SUCCESS_RUNTIME_HEALTHS:
            stabilized = self._upsert_if_changed(
                refreshed,
                reconcile_state='steady',
                restart_count=restart_count,
                last_reconcile_at=attempted_at,
                last_failure_reason=None,
                lifecycle_state=refreshed.state.value,
            )
            self._event_store.append(
                SupervisionEvent(
                    event_kind='recover_succeeded',
                    project_id=self._project_id,
                    agent_name=agent_name,
                    occurred_at=attempted_at,
                    daemon_generation=stabilized.daemon_generation,
                    desired_state=stabilized.desired_state,
                    reconcile_state=stabilized.reconcile_state,
                    prior_health=prior_health,
                    result_health=next_health,
                    runtime_state=stabilized.state.value,
                    runtime_ref=stabilized.runtime_ref,
                    session_ref=stabilized.session_ref,
                    details={'restart_count': stabilized.restart_count},
                )
            )
            return stabilized.health

        failure_runtime = self._upsert_if_changed(
            refreshed,
            reconcile_state='degraded',
            restart_count=restart_count,
            last_reconcile_at=attempted_at,
            last_failure_reason=failure_reason or next_health or prior_health or 'recover-failed',
            lifecycle_state='degraded' if refreshed.state is AgentState.DEGRADED else refreshed.lifecycle_state,
        )
        self._event_store.append(
            SupervisionEvent(
                event_kind='recover_failed',
                project_id=self._project_id,
                agent_name=agent_name,
                occurred_at=attempted_at,
                daemon_generation=failure_runtime.daemon_generation,
                desired_state=failure_runtime.desired_state,
                reconcile_state=failure_runtime.reconcile_state,
                prior_health=prior_health,
                result_health=next_health,
                runtime_state=failure_runtime.state.value,
                runtime_ref=failure_runtime.runtime_ref,
                session_ref=failure_runtime.session_ref,
                details={'reason': failure_runtime.last_failure_reason or 'recover-failed'},
            )
        )
        return failure_runtime.health

    def _ensure_mounted(self, agent_name: str, *, runtime):
        if self._mount_agent_fn is None and self._remount_project_fn is None:
            return 'unmounted' if runtime is None else runtime.health
        attempted_at = self._clock()
        if runtime is not None and self._is_in_backoff_window(runtime, now=attempted_at):
            return runtime.health
        starting = self._build_starting_runtime(agent_name, runtime=runtime, attempted_at=attempted_at)
        self._event_store.append(
            SupervisionEvent(
                event_kind='mount_started',
                project_id=self._project_id,
                agent_name=agent_name,
                occurred_at=attempted_at,
                daemon_generation=starting.daemon_generation,
                desired_state=starting.desired_state,
                reconcile_state=starting.reconcile_state,
                prior_health=runtime.health if runtime is not None else 'unmounted',
                result_health=starting.health,
                runtime_state=starting.state.value,
                runtime_ref=starting.runtime_ref,
                session_ref=starting.session_ref,
            )
        )
        next_restart_count = starting.restart_count + 1
        try:
            if self._should_reflow_project_mount(agent_name):
                self._remount_project_fn(f'mount_recovery:{agent_name}')
            else:
                self._mount_agent_fn(agent_name)
        except Exception as exc:
            failed = self._upsert_if_changed(
                starting,
                state=AgentState.FAILED,
                health='start-failed',
                lifecycle_state='failed',
                reconcile_state='failed',
                restart_count=next_restart_count,
                last_reconcile_at=attempted_at,
                last_failure_reason=f'{type(exc).__name__}: {exc}',
            )
            self._event_store.append(
                SupervisionEvent(
                    event_kind='mount_failed',
                    project_id=self._project_id,
                    agent_name=agent_name,
                    occurred_at=attempted_at,
                    daemon_generation=failed.daemon_generation,
                    desired_state=failed.desired_state,
                    reconcile_state=failed.reconcile_state,
                    prior_health=runtime.health if runtime is not None else 'unmounted',
                    result_health=failed.health,
                    runtime_state=failed.state.value,
                    runtime_ref=failed.runtime_ref,
                    session_ref=failed.session_ref,
                    details={'reason': failed.last_failure_reason or 'mount-failed'},
                )
            )
            return failed.health
        refreshed = self._registry.get(agent_name)
        if refreshed is None:
            return self._persist_mount_failure(
                starting,
                agent_name=agent_name,
                attempted_at=attempted_at,
                prior_health=runtime.health if runtime is not None else 'unmounted',
                next_restart_count=next_restart_count,
                reason='runtime-missing-after-mount',
            )
        refreshed = self._align_runtime_authority(refreshed)
        refreshed_health = normalized_runtime_health(refreshed) or refreshed.health
        if refreshed_health not in _SUCCESS_RUNTIME_HEALTHS:
            return self._persist_mount_failure(
                refreshed,
                agent_name=agent_name,
                attempted_at=attempted_at,
                prior_health=runtime.health if runtime is not None else 'unmounted',
                next_restart_count=next_restart_count,
                reason=refreshed_health or 'mount-produced-unhealthy-runtime',
            )
        mounted = self._upsert_if_changed(
            refreshed,
            state=AgentState.IDLE if refreshed.state is AgentState.STARTING else refreshed.state,
            reconcile_state='steady',
            restart_count=next_restart_count,
            last_reconcile_at=attempted_at,
            last_failure_reason=None,
            lifecycle_state='idle' if refreshed.state is AgentState.STARTING else refreshed.lifecycle_state,
        )
        self._event_store.append(
            SupervisionEvent(
                event_kind='mount_succeeded',
                project_id=self._project_id,
                agent_name=agent_name,
                occurred_at=attempted_at,
                daemon_generation=mounted.daemon_generation,
                desired_state=mounted.desired_state,
                reconcile_state=mounted.reconcile_state,
                prior_health=runtime.health if runtime is not None else 'unmounted',
                result_health=mounted.health,
                runtime_state=mounted.state.value,
                runtime_ref=mounted.runtime_ref,
                session_ref=mounted.session_ref,
                details={'restart_count': mounted.restart_count},
            )
        )
        return mounted.health

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
        failed = self._upsert_if_changed(
            runtime,
            state=AgentState.FAILED,
            health='start-failed',
            lifecycle_state='failed',
            reconcile_state='failed',
            restart_count=next_restart_count,
            last_reconcile_at=attempted_at,
            last_failure_reason=reason,
        )
        self._event_store.append(
            SupervisionEvent(
                event_kind='mount_failed',
                project_id=self._project_id,
                agent_name=agent_name,
                occurred_at=attempted_at,
                daemon_generation=failed.daemon_generation,
                desired_state=failed.desired_state,
                reconcile_state=failed.reconcile_state,
                prior_health=prior_health,
                result_health=failed.health,
                runtime_state=failed.state.value,
                runtime_ref=failed.runtime_ref,
                session_ref=failed.session_ref,
                details={'reason': failed.last_failure_reason or reason},
            )
        )
        return failed.health

    def _align_runtime_authority(self, runtime):
        next_generation = self._generation_getter()
        daemon_generation = runtime.daemon_generation if next_generation is None else next_generation
        desired_state = 'stopped' if runtime.state is AgentState.STOPPED else 'mounted'
        reconcile_state = runtime.reconcile_state
        if runtime.state is AgentState.STOPPED:
            reconcile_state = 'stopped'
        elif runtime.state is AgentState.FAILED:
            reconcile_state = 'failed'
        elif runtime.state is AgentState.DEGRADED and reconcile_state == 'steady':
            reconcile_state = 'degraded'
        elif runtime.state in {AgentState.STARTING, AgentState.IDLE, AgentState.BUSY} and reconcile_state in {
            None,
            '',
            'degraded',
            'recovering',
            'failed',
            'stopped',
        }:
            reconcile_state = 'steady'
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
        spec = self._registry.spec_for(agent_name)
        workspace_path = str(self._layout.workspace_path(agent_name, workspace_root=spec.workspace_root))
        if runtime is None:
            return self._registry.upsert(
                replace(
                    self._runtime_service.attach(
                        agent_name=agent_name,
                        workspace_path=workspace_path,
                        backend_type=spec.runtime_mode.value,
                        health='starting',
                        provider=spec.provider,
                        lifecycle_state='starting',
                        managed_by='ccbd',
                        binding_source='provider-session',
                    ),
                    state=AgentState.STARTING,
                    health='starting',
                    lifecycle_state='starting',
                    daemon_generation=self._generation_getter(),
                    desired_state='mounted',
                    reconcile_state='starting',
                    last_reconcile_at=attempted_at,
                )
            )
        return self._upsert_if_changed(
            runtime,
            state=AgentState.STARTING,
            health='starting',
            workspace_path=runtime.workspace_path or workspace_path,
            backend_type=runtime.backend_type or spec.runtime_mode.value,
            provider=runtime.provider or spec.provider,
            lifecycle_state='starting',
            daemon_generation=self._generation_getter(),
            desired_state='mounted',
            reconcile_state='starting',
            last_reconcile_at=attempted_at,
        )

    def _is_in_backoff_window(self, runtime, *, now: str) -> bool:
        if not str(runtime.last_failure_reason or '').strip():
            return False
        if not str(runtime.last_reconcile_at or '').strip():
            return False
        try:
            checked_at = parse_utc_timestamp(now)
            prior_attempt_at = parse_utc_timestamp(runtime.last_reconcile_at)
        except Exception:
            return False
        delay_s = _backoff_delay_seconds(runtime.restart_count)
        return checked_at < (prior_attempt_at + timedelta(seconds=delay_s))

    def _should_reflow_project_namespace(self, runtime) -> bool:
        if normalized_runtime_health(runtime) not in {'pane-dead', 'pane-missing', 'pane-foreign'}:
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
        try:
            spec = self._registry.spec_for(agent_name)
        except Exception:
            return False
        if getattr(spec, 'runtime_mode', None) is not RuntimeMode.PANE_BACKED:
            return False
        for other_name in self._config.agents:
            other = self._registry.get(other_name)
            if other is None or other.agent_name == agent_name:
                continue
            if other.state is AgentState.BUSY:
                return False
        return True


def _backoff_delay_seconds(restart_count: int) -> int:
    failures = max(1, int(restart_count or 0))
    return min(2 ** (failures - 1), 30)


def _same_socket_path(left: str, right: str) -> bool:
    left_text = str(left or '').strip()
    right_text = str(right or '').strip()
    if not left_text or not right_text:
        return False
    try:
        return Path(left_text).expanduser().resolve() == Path(right_text).expanduser().resolve()
    except Exception:
        return left_text == right_text


__all__ = ['RuntimeSupervisionLoop']
