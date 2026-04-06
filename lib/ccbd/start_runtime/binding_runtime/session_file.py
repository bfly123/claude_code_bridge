from __future__ import annotations

import json
from pathlib import Path


def declared_binding_tmux_socket_path(binding) -> tuple[bool, str | None]:
    session_file = str(getattr(binding, 'session_file', None) or '').strip()
    if session_file:
        try:
            payload = json.loads(Path(session_file).read_text(encoding='utf-8-sig'))
        except Exception:
            payload = None
        if isinstance(payload, dict) and 'tmux_socket_path' in payload:
            text = str(payload.get('tmux_socket_path') or '').strip()
            return True, text or None
        return False, None
    text = str(getattr(binding, 'tmux_socket_path', None) or '').strip()
    return bool(text), text or None


__all__ = ['declared_binding_tmux_socket_path']
