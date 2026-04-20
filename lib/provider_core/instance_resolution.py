from __future__ import annotations


def named_agent_instance(agent_name: str, *, primary_agent: str) -> str | None:
    del primary_agent
    normalized_agent = str(agent_name or "").strip().lower()
    return normalized_agent or None


def should_fallback_to_primary_session(*, agent_name: str, primary_agent: str) -> bool:
    del primary_agent
    return not bool(named_agent_instance(agent_name, primary_agent=""))


__all__ = ["named_agent_instance", "should_fallback_to_primary_session"]
