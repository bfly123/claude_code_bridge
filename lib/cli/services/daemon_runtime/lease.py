from __future__ import annotations


def mark_inspected_lease_unmounted(manager, inspection):
    lease = getattr(inspection, 'lease', None)
    expected_pid = _expected_pid(lease)
    expected_daemon_instance_id = _expected_daemon_instance_id(lease)
    try:
        return manager.mark_unmounted(
            expected_pid=expected_pid,
            expected_daemon_instance_id=expected_daemon_instance_id,
        )
    except RuntimeError:
        load_state = getattr(manager, 'load_state', None)
        if callable(load_state):
            return load_state()
        return None


def _expected_pid(lease) -> int | None:
    try:
        pid = int(getattr(lease, 'ccbd_pid', 0) or 0)
    except Exception:
        return None
    if pid <= 0:
        return None
    return pid


def _expected_daemon_instance_id(lease) -> str | None:
    value = str(getattr(lease, 'daemon_instance_id', '') or '').strip()
    return value or None


__all__ = ['mark_inspected_lease_unmounted']
