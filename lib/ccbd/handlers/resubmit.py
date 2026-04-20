from __future__ import annotations


def build_resubmit_handler(dispatcher):
    def handle(payload: dict) -> dict:
        message_id = str(payload.get('message_id') or '').strip()
        if not message_id:
            raise ValueError('resubmit requires message_id')
        return dispatcher.resubmit(message_id)

    return handle
