from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .tmux_backend import TmuxBackend


class PsmuxBackend(TmuxBackend):
    def __init__(self, *, socket_name: str | None = None, socket_path: str | None = None):
        super().__init__(socket_name=socket_name, socket_path=socket_path)
        if self._socket_name is None and self._socket_path:
            self._socket_name = _psmux_server_name_from_path(self._socket_path)

    @property
    def backend_impl(self) -> str:
        return 'psmux'

    @property
    def backend_ref(self) -> str | None:
        return str(self._socket_name or '').strip() or None

    def _tmux_base(self) -> list[str]:
        executable = str(os.environ.get('CCB_PSMUX_BIN') or 'psmux').strip() or 'psmux'
        command = [executable]
        if self._socket_name:
            command.extend(['-L', self._socket_name])
        return command

    def kill_session(self, session_name: str) -> bool:
        if self._socket_name:
            try:
                self._tmux_run(['kill-server'], check=False)
                return True
            except Exception:
                return False
        return super().kill_session(session_name)


def _psmux_server_name_from_path(socket_path: str) -> str:
    raw = str(socket_path or '').strip()
    if not raw:
        return 'default'
    stem = Path(raw).name or 'ccb'
    safe_stem = ''.join(ch if ch.isalnum() or ch in {'-', '_', '.'} else '-' for ch in stem).strip('-.') or 'ccb'
    digest = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]
    return f'{safe_stem}-{digest}'


__all__ = ['PsmuxBackend']
