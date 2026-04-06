from __future__ import annotations

from .queue import start_next_queued_job
from .recovery import iter_runnable_agent_slots


def iter_runnable_slots(dispatcher):
    yield from iter_runnable_agent_slots(dispatcher)


def tick_jobs(dispatcher):
    started: list = []
    for slot in iter_runnable_slots(dispatcher):
        running = start_next_queued_job(dispatcher, slot)
        if running is not None:
            started.append(running)
    return tuple(started)


__all__ = ['tick_jobs']
