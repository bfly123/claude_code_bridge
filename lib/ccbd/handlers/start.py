from __future__ import annotations


def build_start_handler(app):
    def handle(payload: dict) -> dict:
        requested = tuple(
            str(item).strip()
            for item in (payload.get('agent_names') or ())
            if str(item).strip()
        )
        summary = app.runtime_supervisor.start(
            agent_names=requested,
            restore=bool(payload.get('restore')),
            auto_permission=bool(payload.get('auto_permission')),
        )
        app.persist_start_policy(
            auto_permission=bool(payload.get('auto_permission')),
            source='start_command',
        )
        return summary.to_record()

    return handle
