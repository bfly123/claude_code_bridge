from __future__ import annotations


def build_queue_handler(dispatcher):
    def handle(payload: dict) -> dict:
        target = str(payload.get('target') or 'all').strip()
        if not target:
            raise ValueError('queue requires target')
        return dispatcher.queue(target)

    return handle
