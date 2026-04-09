from __future__ import annotations


def registry_status(registry) -> dict:
    with registry._lock:
        return {
            'total': len(registry._sessions),
            'valid': sum(1 for entry in registry._sessions.values() if entry.valid),
            'sessions': [
                {
                    'work_dir': str(entry.work_dir),
                    'valid': entry.valid,
                }
                for entry in registry._sessions.values()
            ],
        }


__all__ = ['registry_status']
