from __future__ import annotations

def build_stop_all_handler(app):
    def handle(payload: dict) -> dict:
        forced = bool(payload.get('force'))
        summary = app.execute_project_stop(
            force=forced,
            trigger='stop_all',
            reason='stop_all',
            clear_start_policy=True,
        )
        return summary.to_record()

    return handle
