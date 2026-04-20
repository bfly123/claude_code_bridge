from __future__ import annotations

from collections.abc import Callable

_req_id_counter = 0


def make_req_id() -> str:
    global _req_id_counter
    import os
    from datetime import datetime

    now = datetime.now()
    ms = now.microsecond // 1000
    _req_id_counter += 1
    return f"{now.strftime('%Y%m%d-%H%M%S')}-{ms:03d}-{os.getpid()}-{_req_id_counter}"


def request_anchor_for_job(job_id: str | None, *, fallback_factory: Callable[[], str] | None = None) -> str:
    anchor = str(job_id or '').strip()
    if anchor:
        return anchor
    if fallback_factory is not None:
        fallback = str(fallback_factory() or '').strip()
        if fallback:
            return fallback
    raise ValueError('request anchor cannot be empty')


__all__ = ['make_req_id', 'request_anchor_for_job']
