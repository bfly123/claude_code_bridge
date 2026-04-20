from __future__ import annotations

from pathlib import Path

from agents.store import AgentRuntimeStore
from ccbd.models import CcbdRuntimeSnapshot


def build_shutdown_runtime_snapshots(*, paths, config, registry) -> tuple[CcbdRuntimeSnapshot, ...]:
    runtime_store = AgentRuntimeStore(paths)
    return tuple(
        snapshot
        for snapshot in (
            snapshot_for_runtime(runtime_store.load_best_effort(agent_name))
            for agent_name in (
                *tuple(sorted(config.agents)),
                *extra_agent_dir_names(paths, tuple(registry.list_known_agents())),
            )
        )
        if snapshot is not None
    )


def best_effort_runtime(*, agent_name: str, configured_agent_names: tuple[str, ...], registry, runtime_store: AgentRuntimeStore):
    if agent_name in configured_agent_names:
        try:
            return registry.get(agent_name)
        except Exception:
            return runtime_store.load_best_effort(agent_name)
    return runtime_store.load_best_effort(agent_name)


def snapshot_for_runtime(runtime) -> CcbdRuntimeSnapshot | None:
    if runtime is None:
        return None
    try:
        return CcbdRuntimeSnapshot.from_runtime(runtime)
    except Exception:
        return None


def extra_agent_dir_names(paths, configured_agent_names: tuple[str, ...]) -> tuple[str, ...]:
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


__all__ = [
    'best_effort_runtime',
    'build_shutdown_runtime_snapshots',
    'extra_agent_dir_names',
    'snapshot_for_runtime',
]
