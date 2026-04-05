from __future__ import annotations


def build_restore_handler(runtime_service):
    def handle(payload: dict) -> dict:
        agent_name = str(payload.get('agent_name') or '').strip()
        if not agent_name:
            raise ValueError('restore requires agent_name')
        return runtime_service.restore(agent_name).to_record()

    return handle
