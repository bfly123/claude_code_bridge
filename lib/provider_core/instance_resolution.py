from __future__ import annotations


def named_agent_instance(agent_name: str, *, primary_agent: str) -> str | None:
    normalized_agent = str(agent_name or "").strip().lower()
    normalized_primary = str(primary_agent or "").strip().lower()
    if normalized_agent and normalized_agent != normalized_primary:
        return normalized_agent
    return None


def should_fallback_to_primary_session(*, agent_name: str, primary_agent: str) -> bool:
    return named_agent_instance(agent_name, primary_agent=primary_agent) is None


__all__ = ["named_agent_instance", "should_fallback_to_primary_session"]
