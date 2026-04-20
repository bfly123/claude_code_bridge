from __future__ import annotations


def build_ack_handler(dispatcher):
    def handle(payload: dict) -> dict:
        agent_name = str(payload.get('agent_name') or '').strip()
        inbound_event_id = str(payload.get('inbound_event_id') or '').strip() or None
        if not agent_name:
            raise ValueError('ack requires agent_name')
        return dispatcher.ack_reply(agent_name, inbound_event_id)

    return handle
