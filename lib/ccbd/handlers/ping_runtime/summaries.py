from __future__ import annotations


def load_restore_summary(restore_report_store) -> dict:
    if restore_report_store is None:
        return {}
    report = restore_report_store.load()
    return report.summary_fields() if report is not None else {}


def load_namespace_summary(namespace_state_store) -> dict:
    if namespace_state_store is None:
        return {}
    state = namespace_state_store.load()
    return state.summary_fields() if state is not None else {}


def load_namespace_event_summary(namespace_event_store) -> dict:
    if namespace_event_store is None:
        return {}
    event = namespace_event_store.load_latest()
    return event.summary_fields() if event is not None else {}


def load_start_policy_summary(start_policy_store) -> dict:
    if start_policy_store is None:
        return {}
    try:
        policy = start_policy_store.load()
    except Exception:
        policy = None
    return policy.summary_fields() if policy is not None else {}


__all__ = [
    'load_namespace_event_summary',
    'load_namespace_summary',
    'load_restore_summary',
    'load_start_policy_summary',
]
