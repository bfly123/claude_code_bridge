from __future__ import annotations

from pathlib import Path

from provider_core.instance_resolution import named_agent_instance


def binding_search_roots(*, workspace_path: Path, project_root: Path | None) -> tuple[Path, ...]:
    roots: list[Path] = []
    for candidate in (project_root, workspace_path):
        if candidate is None:
            continue
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate.absolute()
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def load_provider_session(*, adapter, provider: str, agent_name: str, roots: tuple[Path, ...], ensure_usable: bool, session_is_usable_fn):
    instance = named_agent_instance(agent_name, primary_agent=provider)
    instances: tuple[str | None, ...] = (instance,) if instance is not None else (None,)

    for root in roots:
        seen_instances: set[str | None] = set()
        for instance_name in instances:
            if instance_name in seen_instances:
                continue
            seen_instances.add(instance_name)
            session = adapter.load_session(root, instance_name)
            if session is None:
                continue
            if not ensure_usable or session_is_usable_fn(session):
                return session
    return None


__all__ = ['binding_search_roots', 'load_provider_session']
