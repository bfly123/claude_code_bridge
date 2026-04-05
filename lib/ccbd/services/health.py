from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from agents.models import AgentState, RuntimeBindingSource, normalize_runtime_binding_source
from ccbd.system import process_exists, utc_now
from provider_core.registry import build_default_session_binding_map
from provider_core.tmux_ownership import inspect_tmux_pane_ownership

from .project_namespace_pane import backend_socket_matches, inspect_project_namespace_pane, same_tmux_socket_path
from .provider_runtime_facts import build_provider_runtime_facts


class HealthMonitor:
    def __init__(
        self,
        registry,
        ownership_guard,
        *,
        clock=utc_now,
        pid_exists=process_exists,
        session_bindings=None,
        namespace_state_store=None,
    ) -> None:
        self._registry = registry
        self._ownership_guard = ownership_guard
        self._clock = clock
        self._pid_exists = pid_exists
        self._session_bindings = session_bindings or build_default_session_binding_map(include_optional=True)
        self._namespace_state_store = namespace_state_store

    def daemon_health(self):
        return self._ownership_guard.inspect()

    def check_all(self) -> dict[str, str]:
        statuses: dict[str, str] = {}
        for runtime in self._registry.list_all():
            status = self._runtime_health(runtime)
            statuses[runtime.agent_name] = status
        return statuses

    def collect_orphans(self) -> tuple[str, ...]:
        statuses = self.check_all()
        return tuple(sorted(name for name, status in statuses.items() if status != 'healthy'))

    def _runtime_health(self, runtime) -> str:
        binding_source = normalize_runtime_binding_source(
            getattr(runtime, 'binding_source', RuntimeBindingSource.PROVIDER_SESSION)
        )
        if runtime.state in {AgentState.STOPPED, AgentState.FAILED}:
            return runtime.health
        pane_status = self._pane_health(runtime)
        if pane_status is not None:
            return pane_status
        if runtime.pid is not None and not self._pid_exists(runtime.pid):
            updated = replace(runtime, state=AgentState.DEGRADED, health='orphaned', last_seen_at=self._clock())
            self._registry.upsert(updated)
            return updated.health
        if binding_source is RuntimeBindingSource.EXTERNAL_ATTACH:
            return runtime.health
        if runtime.state is AgentState.DEGRADED:
            return runtime.health
        if runtime.health not in {'healthy', 'restored'}:
            updated = replace(runtime, health='healthy', last_seen_at=self._clock())
            self._registry.upsert(updated)
            return updated.health
        return runtime.health

    def _pane_health(self, runtime) -> str | None:
        binding_source = normalize_runtime_binding_source(
            getattr(runtime, 'binding_source', RuntimeBindingSource.PROVIDER_SESSION)
        )
        if binding_source is RuntimeBindingSource.EXTERNAL_ATTACH:
            return None
        return self._provider_pane_health(runtime)

    def _provider_pane_health(self, runtime) -> str | None:
        runtime_ref = str(runtime.runtime_ref or '').strip()
        if not runtime_ref.startswith('tmux:'):
            return None
        spec = self._registry.spec_for(runtime.agent_name)
        binding = self._session_bindings.get(spec.provider)
        if binding is None:
            return None
        workspace_path = str(runtime.workspace_path or '').strip()
        if not workspace_path:
            return None
        try:
            session = binding.load_session(Path(workspace_path), runtime.agent_name)
        except Exception:
            session = None
        if session is None:
            try:
                session = binding.load_session(Path(workspace_path), None)
            except Exception:
                session = None
        if session is None:
            updated = self._mark_degraded(runtime, health='session-missing')
            return updated.health

        terminal = str(getattr(session, 'terminal', '') or '').strip().lower()
        if terminal != 'tmux':
            refreshed = self._rebind_runtime(runtime, session, binding)
            return refreshed.health

        backend = self._session_backend(session)
        pane_id = str(getattr(session, 'pane_id', '') or '').strip()
        pane_state = self._tmux_pane_state(session, backend, pane_id)
        if pane_state == 'alive' and self._pane_outside_project_namespace(runtime, backend, pane_id):
            pane_state = 'foreign'
        if pane_state == 'alive':
            refreshed = self._rebind_runtime(runtime, session, binding)
            return refreshed.health
        if pane_state == 'foreign':
            updated = self._mark_degraded(runtime, health='pane-foreign', session=session, binding=binding)
            return updated.health

        if pane_state == 'missing':
            health = 'pane-missing'
        elif pane_state == 'foreign':
            health = 'pane-foreign'
        else:
            health = 'pane-dead'
        updated = self._mark_degraded(runtime, health=health, session=session, binding=binding)
        return updated.health

    @staticmethod
    def _session_backend(session):
        resolver = getattr(session, 'backend', None)
        if not callable(resolver):
            return None
        try:
            return resolver()
        except Exception:
            return None

    @staticmethod
    def _tmux_pane_state(session, backend, pane_id: str) -> str:
        pane_id = str(pane_id or '').strip()
        if backend is None or not pane_id:
            return 'missing'
        pane_exists = getattr(backend, 'pane_exists', None)
        if callable(pane_exists):
            try:
                if not pane_exists(pane_id):
                    return 'missing'
            except Exception:
                return 'missing'
        ownership = inspect_tmux_pane_ownership(session, backend, pane_id)
        if not ownership.is_owned:
            return 'foreign'
        pane_alive = getattr(backend, 'is_tmux_pane_alive', None)
        if callable(pane_alive):
            try:
                return 'alive' if pane_alive(pane_id) else 'dead'
            except Exception:
                return 'missing'
        is_alive = getattr(backend, 'is_alive', None)
        if callable(is_alive):
            try:
                return 'alive' if is_alive(pane_id) else 'dead'
            except Exception:
                return 'missing'
        return 'missing'

    def _pane_outside_project_namespace(self, runtime, backend, pane_id: str) -> bool:
        pane_text = str(pane_id or '').strip()
        if backend is None or not pane_text.startswith('%'):
            return False
        if self._namespace_state_store is None:
            return False
        try:
            namespace_state = self._namespace_state_store.load()
        except Exception:
            namespace_state = None
        if namespace_state is None:
            return False
        if not backend_socket_matches(backend, namespace_state.tmux_socket_path):
            runtime_socket = str(getattr(runtime, 'tmux_socket_path', None) or '').strip()
            if runtime_socket and same_tmux_socket_path(runtime_socket, namespace_state.tmux_socket_path):
                return True
            return False
        record = inspect_project_namespace_pane(backend, pane_text)
        if record is None:
            return True
        return not record.matches(
            tmux_session_name=namespace_state.tmux_session_name,
            project_id=runtime.project_id,
            role='agent',
            slot_key=runtime.agent_name,
            managed_by='ccbd',
        )

    def _rebind_runtime(
        self,
        runtime,
        session,
        binding,
        *,
        pane_id_override: str | None = None,
        force_session_ref_update: bool = False,
    ):
        facts = self._provider_runtime_facts(
            runtime,
            session,
            binding,
            pane_id_override=pane_id_override,
        )
        pane_id = facts.pane_id if facts is not None else str(pane_id_override or getattr(session, 'pane_id', '') or '').strip() or None
        next_runtime_ref = facts.runtime_ref if facts is not None and facts.runtime_ref else runtime.runtime_ref
        session_ref = facts.session_ref if facts is not None else self._session_ref(session, binding)
        next_session_ref = session_ref if force_session_ref_update else (runtime.session_ref or session_ref)
        next_state = runtime.state if runtime.state is not AgentState.DEGRADED else AgentState.IDLE
        next_health = 'healthy'
        if runtime.state is not AgentState.DEGRADED and runtime.health == 'restored':
            next_health = 'restored'
        updated = replace(
            runtime,
            state=next_state,
            pid=facts.runtime_pid if facts is not None and facts.runtime_pid is not None else runtime.pid,
            runtime_ref=next_runtime_ref,
            session_ref=next_session_ref,
            health=next_health,
            runtime_root=facts.runtime_root if facts is not None and facts.runtime_root is not None else runtime.runtime_root,
            runtime_pid=facts.runtime_pid if facts is not None and facts.runtime_pid is not None else runtime.runtime_pid,
            terminal_backend=facts.terminal_backend if facts is not None and facts.terminal_backend is not None else runtime.terminal_backend,
            pane_id=pane_id or runtime.pane_id,
            active_pane_id=pane_id or runtime.active_pane_id,
            pane_title_marker=(
                facts.pane_title_marker
                if facts is not None and facts.pane_title_marker is not None
                else runtime.pane_title_marker
            ),
            pane_state='alive',
            tmux_socket_name=facts.tmux_socket_name if facts is not None and facts.tmux_socket_name is not None else runtime.tmux_socket_name,
            tmux_socket_path=facts.tmux_socket_path if facts is not None and facts.tmux_socket_path is not None else runtime.tmux_socket_path,
            session_file=facts.session_file if facts is not None and facts.session_file is not None else runtime.session_file,
            session_id=facts.session_id if facts is not None and facts.session_id is not None else runtime.session_id,
            last_seen_at=self._clock(),
        )
        return self._registry.upsert(updated)

    def _mark_degraded(self, runtime, *, health: str, session=None, binding=None):
        next_runtime_ref = runtime.runtime_ref
        next_session_ref = runtime.session_ref
        next_runtime_root = runtime.runtime_root
        next_runtime_pid = runtime.runtime_pid
        next_terminal_backend = runtime.terminal_backend
        next_pane_id = runtime.pane_id
        next_active_pane_id = runtime.active_pane_id
        next_pane_title_marker = runtime.pane_title_marker
        next_tmux_socket_name = runtime.tmux_socket_name
        next_tmux_socket_path = runtime.tmux_socket_path
        next_session_file = runtime.session_file
        next_session_id = runtime.session_id
        if session is not None:
            facts = self._provider_runtime_facts(runtime, session, binding) if binding is not None else None
            if facts is not None:
                if facts.runtime_ref:
                    next_runtime_ref = facts.runtime_ref
                if facts.session_ref:
                    next_session_ref = facts.session_ref
                next_runtime_root = facts.runtime_root or next_runtime_root
                next_runtime_pid = facts.runtime_pid if facts.runtime_pid is not None else next_runtime_pid
                next_terminal_backend = facts.terminal_backend or next_terminal_backend
                next_pane_id = facts.pane_id or next_pane_id
                next_active_pane_id = facts.pane_id or next_active_pane_id
                next_pane_title_marker = facts.pane_title_marker or next_pane_title_marker
                next_tmux_socket_name = facts.tmux_socket_name or next_tmux_socket_name
                next_tmux_socket_path = facts.tmux_socket_path or next_tmux_socket_path
                next_session_file = facts.session_file or next_session_file
                next_session_id = facts.session_id or next_session_id
            else:
                bound_runtime_ref = self._runtime_ref(session)
                if bound_runtime_ref:
                    next_runtime_ref = bound_runtime_ref
                if binding is not None:
                    bound_session_ref = self._session_ref(session, binding)
                    if bound_session_ref:
                        next_session_ref = bound_session_ref
                pane_id = str(getattr(session, 'pane_id', '') or '').strip()
                if pane_id:
                    next_pane_id = pane_id
                    next_active_pane_id = pane_id
                terminal = str(getattr(session, 'terminal', '') or '').strip()
                if terminal:
                    next_terminal_backend = terminal
                pane_title_marker = str(getattr(session, 'pane_title_marker', '') or '').strip()
                if pane_title_marker:
                    next_pane_title_marker = pane_title_marker
        next_pane_state = runtime.pane_state
        if health in {'pane-dead', 'orphaned'}:
            next_pane_state = 'dead'
        elif health in {'pane-missing', 'session-missing'}:
            next_pane_state = 'missing'
        elif health == 'pane-foreign':
            next_pane_state = 'foreign'
            next_active_pane_id = None
        updated = replace(
            runtime,
            state=AgentState.DEGRADED,
            runtime_ref=next_runtime_ref,
            session_ref=next_session_ref,
            health=health,
            runtime_root=next_runtime_root,
            runtime_pid=next_runtime_pid,
            terminal_backend=next_terminal_backend,
            pane_id=next_pane_id,
            active_pane_id=next_active_pane_id,
            pane_title_marker=next_pane_title_marker,
            pane_state=next_pane_state,
            tmux_socket_name=next_tmux_socket_name,
            tmux_socket_path=next_tmux_socket_path,
            session_file=next_session_file,
            session_id=next_session_id,
            last_seen_at=self._clock(),
        )
        return self._registry.upsert(updated)

    def _provider_runtime_facts(self, runtime, session, binding, *, pane_id_override: str | None = None):
        provider = str(getattr(runtime, 'provider', '') or '').strip()
        if not provider:
            try:
                provider = str(self._registry.spec_for(runtime.agent_name).provider or '').strip()
            except Exception:
                provider = ''
        if not provider:
            return None
        try:
            return build_provider_runtime_facts(
                session,
                binding=binding,
                provider=provider,
                pane_id_override=pane_id_override,
            )
        except Exception:
            return None

    @staticmethod
    def _runtime_ref(session) -> str | None:
        pane_id = str(getattr(session, 'pane_id', '') or '').strip()
        terminal = str(getattr(session, 'terminal', '') or '').strip() or 'tmux'
        if pane_id:
            return f'{terminal}:{pane_id}'
        return None

    @staticmethod
    def _session_ref(session, binding) -> str | None:
        value = getattr(session, binding.session_id_attr, None)
        text = str(value or '').strip()
        if text:
            return text
        value = getattr(session, binding.session_path_attr, None)
        text = str(value or '').strip()
        if text:
            return text
        session_file = getattr(session, 'session_file', None)
        if session_file:
            return str(session_file)
        return None


__all__ = ['HealthMonitor']
