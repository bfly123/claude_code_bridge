from __future__ import annotations

def build_shutdown_handler(app):
    def handle(payload: dict) -> dict:
        del payload
        summary = app.execute_project_stop(
            force=False,
            trigger='shutdown',
            reason='shutdown',
            clear_start_policy=True,
        )
        return summary.to_record()

    return handle
