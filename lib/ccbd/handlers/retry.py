from __future__ import annotations


def build_retry_handler(dispatcher):
    def handle(payload: dict) -> dict:
        target = str(payload.get('target') or '').strip()
        if not target:
            raise ValueError('retry requires target')
        return dispatcher.retry(target)

    return handle
