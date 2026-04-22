from __future__ import annotations

from dataclasses import fields, replace

from agents.models import AgentRuntime, AgentSpec, AgentState, normalize_agent_name
from agents.store import AgentRuntimeStore
from provider_runtime.helper_cleanup import cleanup_stale_runtime_helper
from provider_runtime.helper_manifest import clear_helper_manifest
from provider_runtime.helper_manifest import sync_runtime_helper_manifest
from storage.paths import PathLayout

_ACTIVE_STATES = {AgentState.STARTING, AgentState.IDLE, AgentState.BUSY, AgentState.DEGRADED}
_STATE_MUTATION_FIELDS = frozenset(
    {
        'state',
        'health',
        'queue_depth',
        'active_pane_id',
        'pane_state',
        'desired_state',
        'reconcile_state',
        'restart_count',
        'last_seen_at',
        'last_reconcile_at',
        'last_failure_reason',
        'lifecycle_state',
        'pid',
    }
)
_RUNTIME_FIELD_NAMES = tuple(field.name for field in fields(AgentRuntime))


class AgentRegistry:
    def __init__(self, layout: PathLayout, config, runtime_store: AgentRuntimeStore | None = None) -> None:
        self._layout = layout
        self._config = config
        self._runtime_store = runtime_store or AgentRuntimeStore(layout)
        self._cache: dict[str, AgentRuntime] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        for agent_name in self._config.agents:
            runtime = self._runtime_store.load(agent_name)
            if runtime is not None:
                self._cache[agent_name] = runtime

    def spec_for(self, agent_name: str) -> AgentSpec:
        normalized = normalize_agent_name(agent_name)
        try:
            return self._config.agents[normalized]
        except KeyError as exc:
            raise KeyError(f'unknown agent: {normalized}') from exc

    def get(self, agent_name: str) -> AgentRuntime | None:
        normalized = normalize_agent_name(agent_name)
        cached = self._cache.get(normalized)
        if cached is not None:
            return cached
        runtime = self._runtime_store.load(normalized)
        if runtime is not None:
            self._cache[normalized] = runtime
        return runtime

    def upsert(self, runtime: AgentRuntime, *, authority_write: bool = False) -> AgentRuntime:
        self.spec_for(runtime.agent_name)
        existing = self.get(runtime.agent_name)
        changed_fields = _changed_runtime_fields(existing, runtime)
        if changed_fields and not authority_write:
            authority_fields = tuple(sorted(set(changed_fields) - _STATE_MUTATION_FIELDS))
            if authority_fields:
                raise ValueError(
                    'authority write required for runtime fields: '
                    + ', '.join(authority_fields)
                )
        cleanup_stale_runtime_helper(self._layout, runtime)
        self._runtime_store.save(runtime)
        sync_runtime_helper_manifest(self._layout, runtime)
        self._cache[runtime.agent_name] = runtime
        return runtime

    def upsert_authority(self, runtime: AgentRuntime) -> AgentRuntime:
        return self.upsert(runtime, authority_write=True)

    def remove(self, agent_name: str) -> AgentRuntime | None:
        runtime = self.get(agent_name)
        if runtime is None:
            clear_helper_manifest(self._layout.agent_helper_path(agent_name))
            return None
        stopped = replace(
            runtime,
            state=AgentState.STOPPED,
            pid=None,
            runtime_ref=None,
            session_ref=None,
            socket_path=None,
            queue_depth=0,
            health='stopped',
            runtime_pid=None,
            pane_id=None,
            active_pane_id=None,
            pane_state=None,
            desired_state='stopped',
            reconcile_state='stopped',
            last_failure_reason=None,
        )
        saved = self.upsert_authority(stopped)
        clear_helper_manifest(self._layout.agent_helper_path(agent_name))
        return saved

    def list_all(self) -> tuple[AgentRuntime, ...]:
        runtimes: list[AgentRuntime] = []
        for agent_name in sorted(self._config.agents):
            runtime = self.get(agent_name)
            if runtime is not None:
                runtimes.append(runtime)
        return tuple(runtimes)

    def list_alive(self) -> tuple[AgentRuntime, ...]:
        return tuple(runtime for runtime in self.list_all() if runtime.state in _ACTIVE_STATES)

    def list_known_agents(self) -> tuple[str, ...]:
        return tuple(sorted(self._config.agents))


def _changed_runtime_fields(existing: AgentRuntime | None, runtime: AgentRuntime) -> tuple[str, ...]:
    if existing is None:
        return ()
    changed: list[str] = []
    for field_name in _RUNTIME_FIELD_NAMES:
        if getattr(existing, field_name) != getattr(runtime, field_name):
            changed.append(field_name)
    return tuple(changed)


__all__ = ['AgentRegistry']
