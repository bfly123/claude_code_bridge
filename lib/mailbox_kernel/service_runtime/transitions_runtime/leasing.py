from __future__ import annotations


def next_lease_version(service, agent_name: str) -> int:
    normalized = service._normalize_agent_name(agent_name)
    lease = service._lease_store.load(normalized)
    if lease is not None:
        return lease.lease_version + 1
    mailbox = service._mailbox_store.load(normalized)
    if mailbox is not None:
        return mailbox.lease_version + 1
    return 1


__all__ = ['next_lease_version']
