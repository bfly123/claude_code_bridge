from __future__ import annotations

from ccbd.api_models import DeliveryScope, MessageEnvelope


def build_submit_handler(dispatcher):
    def handle(payload: dict) -> dict:
        envelope = MessageEnvelope(
            project_id=payload['project_id'],
            to_agent=payload['to_agent'],
            from_actor=payload['from_actor'],
            body=payload['body'],
            task_id=payload.get('task_id'),
            reply_to=payload.get('reply_to'),
            message_type=payload.get('message_type', 'ask'),
            delivery_scope=DeliveryScope(payload.get('delivery_scope', DeliveryScope.SINGLE.value)),
            silence_on_success=bool(payload.get('silence_on_success', False)),
        )
        return dispatcher.submit(envelope).to_record()

    return handle
