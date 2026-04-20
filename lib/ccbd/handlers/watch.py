from __future__ import annotations


def build_watch_handler(dispatcher, *, health_monitor=None):
    def handle(payload: dict) -> dict:
        target = str(payload.get('target') or '').strip()
        if not target:
            raise ValueError('watch requires target')
        start_line = int(payload.get('cursor') or 0)
        if start_line < 0:
            raise ValueError('watch cursor cannot be negative')
        result = dispatcher.watch(target, start_line=start_line)
        if health_monitor is not None:
            inspection = health_monitor.daemon_health()
            result['generation'] = inspection.generation
        return result

    return handle
