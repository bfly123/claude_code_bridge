from __future__ import annotations

import os

from .tmux_backend import TmuxBackend


class PsmuxBackend(TmuxBackend):
    @property
    def backend_impl(self) -> str:
        return 'psmux'

    @property
    def backend_ref(self) -> str | None:
        return str(self._socket_path or self._socket_name or '').strip() or None

    def _tmux_base(self) -> list[str]:
        executable = str(os.environ.get('CCB_PSMUX_BIN') or 'psmux').strip() or 'psmux'
        return [executable]


__all__ = ['PsmuxBackend']
