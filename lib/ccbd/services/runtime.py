from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from agents.models import AgentRuntime, AgentState, AgentValidationError, RestoreStatus, RuntimeBindingSource, normalize_runtime_binding_source
from agents.runtime_binding import merge_runtime_binding, runtime_binding_from_runtime
from agents.store import AgentRestoreStore
from ccbd.system import utc_now
from provider_core.registry import build_default_session_binding_map
from storage.paths import PathLayout

from .provider_runtime_facts import build_provider_runtime_facts, ensure_provider_pane, load_provider_session
from .registry import AgentRegistry
from .runtime_attach import (
    binding_source_for_attach,
    normalized_text,
    pane_id_from_runtime_ref,
    resolve_session_fields,
    state_for_attach,
    terminal_backend_from_runtime_ref,
)

_ACTIVE_STATES = {AgentState.STARTING, AgentState.IDLE, AgentState.BUSY, AgentState.DEGRADED}


class RuntimeService:
    def __init__(
        self,
        layout: PathLayout,
        registry: AgentRegistry,
        project_id: str,
        restore_store: AgentRestoreStore | None = None,
        session_bindings=None,
        *,
        clock=utc_now,
    ) -> None:
        self._layout = layout
        self._registry = registry
        self._project_id = project_id
        self._restore_store = restore_store or AgentRestoreStore(layout)
        self._session_bindings = session_bindings or build_default_session_binding_map(include_optional=True)
        self._clock = clock

    def attach(
        self,
        *,
        agent_name: str,
        workspace_path: str,
        backend_type: str,
        pid: int | None = None,
        runtime_ref: str | None = None,
        session_ref: str | None = None,
        health: str | None = None,
        provider: str | None = None,
        runtime_root: str | None = None,
        runtime_pid: int | None = None,
        terminal_backend: str | None = None,
        pane_id: str | None = None,
        active_pane_id: str | None = None,
        pane_title_marker: str | None = None,
        pane_state: str | None = None,
        tmux_socket_name: str | None = None,
        tmux_socket_path: str | None = None,
        session_file: str | None = None,
        session_id: str | None = None,
        lifecycle_state: str | None = None,
        managed_by: str | None = None,
        binding_source: str | RuntimeBindingSource | None = None,
    ) -> AgentRuntime:
        spec = self._registry.spec_for(agent_name)
        existing = self._registry.get(agent_name)
        timestamp = self._clock()
        next_binding_source = binding_source_for_attach(existing, explicit=binding_source)
        next_health = health or (existing.health if existing is not None else 'healthy')
        next_provider = str(provider or (existing.provider if existing is not None else spec.provider) or '').strip() or spec.provider
        merged_binding = merge_runtime_binding(
            runtime_binding_from_runtime(existing),
            runtime_ref=runtime_ref,
            session_ref=session_ref,
            workspace_path=workspace_path,
        )
        session_file_value, session_id_value, session_ref_value = resolve_session_fields(
            existing,
            session_ref=merged_binding.session_ref,
            session_file=session_file,
            session_id=session_id,
            session_ref_explicit=session_ref is not None,
            session_file_explicit=session_file is not None,
            session_id_explicit=session_id is not None,
        )
        runtime_ref_value = merged_binding.runtime_ref
        terminal_backend_value = (
            normalized_text(terminal_backend)
            or terminal_backend_from_runtime_ref(runtime_ref_value)
            or (existing.terminal_backend if existing is not None else None)
        )
        pane_id_value = (
            normalized_text(pane_id)
            or pane_id_from_runtime_ref(runtime_ref_value)
            or (existing.pane_id if existing is not None else None)
        )
        active_pane_id_value = (
            normalized_text(active_pane_id)
            or pane_id_value
            or (existing.active_pane_id if existing is not None else None)
        )
        binding_generation = (existing.binding_generation + 1) if existing is not None else 1
        next_state = state_for_attach(existing.state if existing is not None else None, next_health)
        next_lifecycle_state = (
            normalized_text(lifecycle_state)
            or (existing.lifecycle_state if existing is not None else None)
            or next_state.value
        )
        next_managed_by = normalized_text(managed_by) or (existing.managed_by if existing is not None else 'ccbd')
        next_runtime_pid = runtime_pid if runtime_pid is not None else pid if pid is not None else (existing.runtime_pid if existing is not None else None)
        next_runtime_root = normalized_text(runtime_root) or (existing.runtime_root if existing is not None else None)
        next_tmux_socket_name = normalized_text(tmux_socket_name) or (existing.tmux_socket_name if existing is not None else None)
        next_tmux_socket_path = normalized_text(tmux_socket_path) or (existing.tmux_socket_path if existing is not None else None)
        next_pane_title_marker = normalized_text(pane_title_marker) or (existing.pane_title_marker if existing is not None else None)
        next_pane_state = normalized_text(pane_state) or (existing.pane_state if existing is not None else None)
        if existing is not None and existing.state in _ACTIVE_STATES:
            updated = replace(
                existing,
                state=next_state,
                last_seen_at=timestamp,
                pid=next_runtime_pid,
                workspace_path=merged_binding.workspace_path,
                backend_type=backend_type or existing.backend_type,
                runtime_ref=runtime_ref_value,
                session_ref=session_ref_value,
                project_id=existing.project_id or self._project_id,
                health=next_health,
                provider=next_provider,
                runtime_root=next_runtime_root,
                runtime_pid=next_runtime_pid,
                terminal_backend=terminal_backend_value,
                pane_id=pane_id_value,
                active_pane_id=active_pane_id_value,
                pane_title_marker=next_pane_title_marker,
                pane_state=next_pane_state,
                tmux_socket_name=next_tmux_socket_name,
                tmux_socket_path=next_tmux_socket_path,
                session_file=session_file_value,
                session_id=session_id_value,
                lifecycle_state=next_lifecycle_state,
                binding_generation=binding_generation,
                managed_by=next_managed_by,
                binding_source=next_binding_source,
            )
            return self._registry.upsert(updated)
        runtime = AgentRuntime(
            agent_name=spec.name,
            state=next_state,
            pid=next_runtime_pid,
            started_at=existing.started_at if existing and existing.started_at else timestamp,
            last_seen_at=timestamp,
            runtime_ref=runtime_ref_value,
            session_ref=session_ref_value,
            workspace_path=merged_binding.workspace_path,
            project_id=existing.project_id if existing else self._project_id,
            backend_type=backend_type,
            queue_depth=existing.queue_depth if existing else 0,
            socket_path=existing.socket_path if existing else None,
            health=next_health,
            provider=next_provider,
            runtime_root=next_runtime_root,
            runtime_pid=next_runtime_pid,
            terminal_backend=terminal_backend_value,
            pane_id=pane_id_value,
            active_pane_id=active_pane_id_value,
            pane_title_marker=next_pane_title_marker,
            pane_state=next_pane_state,
            tmux_socket_name=next_tmux_socket_name,
            tmux_socket_path=next_tmux_socket_path,
            session_file=session_file_value,
            session_id=session_id_value,
            lifecycle_state=next_lifecycle_state,
            binding_generation=binding_generation,
            managed_by=next_managed_by,
            binding_source=next_binding_source,
        )
        return self._registry.upsert(runtime)

    def restore(self, agent_name: str):
        spec = self._registry.spec_for(agent_name)
        state = self._restore_store.load(spec.name)
        runtime = self._registry.get(spec.name)
        if state is None:
            raise AgentValidationError(f'no restore state for agent {spec.name}')
        timestamp = self._clock()
        if runtime is not None and runtime.state in _ACTIVE_STATES:
            updated_runtime = replace(runtime, last_seen_at=timestamp, health='restored')
            self._registry.upsert(updated_runtime)
        else:
            self.attach(
                agent_name=spec.name,
                workspace_path=(
                    runtime.workspace_path if runtime is not None and runtime.workspace_path else str(self._layout.workspace_path(spec.name))
                ),
                backend_type=runtime.backend_type if runtime is not None else spec.runtime_mode.value,
                pid=runtime.pid if runtime is not None else None,
                runtime_ref=runtime.runtime_ref if runtime is not None else None,
                session_ref=runtime.session_ref if runtime is not None else None,
                health='restored',
                binding_source=runtime.binding_source if runtime is not None else RuntimeBindingSource.PROVIDER_SESSION,
            )
        updated_state = replace(
            state,
            last_restore_status=RestoreStatus.CHECKPOINT if state.last_checkpoint else RestoreStatus.FRESH,
        )
        self._restore_store.save(spec.name, updated_state)
        return updated_state

    def ensure_ready(self, agent_name: str) -> AgentRuntime:
        spec = self._registry.spec_for(agent_name)
        runtime = self._registry.get(spec.name)
        if runtime is not None and runtime.state in _ACTIVE_STATES:
            updated = replace(runtime, last_seen_at=self._clock())
            return self._registry.upsert(updated)

        restore_state = self._restore_store.load(spec.name)
        if runtime is None and restore_state is None:
            raise AgentValidationError(f'agent {spec.name} has no runtime or restore state; start it first')

        attached = self.attach(
            agent_name=spec.name,
            workspace_path=(
                runtime.workspace_path if runtime is not None and runtime.workspace_path else str(self._layout.workspace_path(spec.name))
            ),
            backend_type=runtime.backend_type if runtime is not None else spec.runtime_mode.value,
            pid=runtime.pid if runtime is not None else None,
            runtime_ref=runtime.runtime_ref if runtime is not None else None,
            session_ref=runtime.session_ref if runtime is not None else None,
            health='restored' if restore_state is not None else 'healthy',
            binding_source=runtime.binding_source if runtime is not None else RuntimeBindingSource.PROVIDER_SESSION,
        )
        if restore_state is not None:
            self.restore(spec.name)
            refreshed = self._registry.get(spec.name)
            if refreshed is not None:
                return refreshed
        return attached

    def refresh_provider_binding(self, agent_name: str, *, recover: bool = False) -> AgentRuntime | None:
        runtime = self._registry.get(agent_name)
        if runtime is None:
            return None
        if normalize_runtime_binding_source(runtime.binding_source) is RuntimeBindingSource.EXTERNAL_ATTACH:
            return runtime
        workspace_path = str(runtime.workspace_path or '').strip()
        if not workspace_path:
            return runtime
        spec = self._registry.spec_for(agent_name)
        binding = self._session_bindings.get(spec.provider)
        if binding is None:
            return runtime

        session = load_provider_session(binding, Path(workspace_path), agent_name)
        if session is None:
            return self.attach(
                agent_name=agent_name,
                workspace_path=workspace_path,
                backend_type=runtime.backend_type,
                pid=runtime.pid,
                runtime_ref=runtime.runtime_ref,
                session_ref=runtime.session_ref,
                health='session-missing',
                binding_source=runtime.binding_source,
            )

        pane_id = str(getattr(session, 'pane_id', '') or '').strip()
        if recover:
            ok, pane_or_err = ensure_provider_pane(session)
            if not ok:
                return runtime
            pane_id = str(pane_or_err or '').strip()
        facts = build_provider_runtime_facts(
            session,
            binding=binding,
            provider=spec.provider,
            pane_id_override=pane_id or None,
        )
        return self.attach(
            agent_name=agent_name,
            workspace_path=workspace_path,
            backend_type=runtime.backend_type,
            pid=runtime.pid,
            runtime_ref=facts.runtime_ref or runtime.runtime_ref,
            session_ref=facts.session_ref or runtime.session_ref,
            health='healthy',
            provider=spec.provider,
            runtime_root=facts.runtime_root,
            runtime_pid=facts.runtime_pid,
            terminal_backend=facts.terminal_backend,
            pane_id=facts.pane_id,
            active_pane_id=pane_id or None,
            pane_title_marker=facts.pane_title_marker,
            pane_state=facts.pane_state,
            tmux_socket_name=facts.tmux_socket_name,
            tmux_socket_path=facts.tmux_socket_path,
            session_file=facts.session_file,
            session_id=facts.session_id,
            binding_source=runtime.binding_source,
        )


__all__ = ['RuntimeService']
