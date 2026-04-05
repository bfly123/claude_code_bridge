from __future__ import annotations


def build_trace_handler(dispatcher):
    def handle(payload: dict) -> dict:
        target = str(payload.get('target') or '').strip()
        if not target:
            raise ValueError('trace requires target')
        return dispatcher.trace(target)

    return handle
