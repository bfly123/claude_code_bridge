from __future__ import annotations

import os

_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_POLL_INTERVAL_S = 0.1


def resolve_timeout(explicit: float | None) -> float:
    if explicit is not None:
        return max(0.1, float(explicit))
    raw = os.environ.get('CCB_WAIT_TIMEOUT_S')
    if raw:
        try:
            return max(0.1, float(raw))
        except Exception:
            pass
    return _DEFAULT_TIMEOUT_S


def resolve_poll_interval() -> float:
    raw = os.environ.get('CCB_WAIT_POLL_INTERVAL_S')
    if raw:
        try:
            return max(0.01, float(raw))
        except Exception:
            pass
    return _DEFAULT_POLL_INTERVAL_S


def resolve_quorum(command, *, expected_count: int) -> int:
    if command.mode == 'quorum':
        quorum = int(command.quorum or 0)
        if quorum > expected_count:
            raise RuntimeError(
                f'wait quorum {quorum} exceeds available reply routes {expected_count} for target {command.target}'
            )
        return quorum
    return 1 if command.mode == 'any' else expected_count


__all__ = ['resolve_poll_interval', 'resolve_quorum', 'resolve_timeout']
