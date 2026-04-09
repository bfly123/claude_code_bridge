from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

from terminal_runtime.backend_types import TerminalBackend
from terminal_runtime.env import subprocess_kwargs as _subprocess_kwargs_impl
from terminal_runtime.tmux import tmux_base as _tmux_base_impl
from terminal_runtime.tmux_backend_control import TmuxBackendControlMixin
from terminal_runtime.tmux_backend_logs import TmuxBackendLogsMixin
from terminal_runtime.tmux_backend_panes import (
    TmuxBackendPaneMutationMixin,
    TmuxBackendPaneQueryMixin,
)
from terminal_runtime.tmux_backend_runtime import (
    TmuxBackendServices,
    build_backend_services as _build_backend_services_impl,
)


def _subprocess_kwargs() -> dict:
    return _subprocess_kwargs_impl()


def _run(*args, **kwargs):
    kwargs.update(_subprocess_kwargs())
    import subprocess as _sp

    return _sp.run(*args, **kwargs)


class TmuxBackend(
    TmuxBackendLogsMixin,
    TmuxBackendPaneQueryMixin,
    TmuxBackendPaneMutationMixin,
    TmuxBackendControlMixin,
    TerminalBackend,
):
    _ANSI_RE = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')

    def __init__(self, *, socket_name: str | None = None, socket_path: str | None = None):
        self._socket_path = (
            socket_path or os.environ.get('CCB_TMUX_SOCKET_PATH') or ''
        ).strip() or None
        if self._socket_path:
            self._socket_path = str(Path(self._socket_path).expanduser())
        self._socket_name = (
            socket_name or os.environ.get('CCB_TMUX_SOCKET') or ''
        ).strip() or None
        self._pane_log_info: dict[str, float] = {}
        self._services: TmuxBackendServices = _build_backend_services_impl(self)

    def _tmux_base(self) -> list[str]:
        return _tmux_base_impl(self._socket_name, socket_path=self._socket_path)

    def _tmux_run(
        self,
        args: list[str],
        *,
        check: bool = False,
        capture: bool = False,
        input_bytes: bytes | None = None,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess:
        kwargs: dict = {}
        if capture:
            kwargs.update(
                {
                    'capture_output': True,
                    'text': True,
                    'encoding': 'utf-8',
                    'errors': 'replace',
                }
            )
        if input_bytes is not None:
            kwargs['input'] = input_bytes
        if timeout is not None:
            kwargs['timeout'] = timeout
        return _run([*self._tmux_base(), *args], check=check, **kwargs)

    @staticmethod
    def _env_tmux_pane() -> str:
        return os.environ.get('TMUX_PANE', '')


__all__ = ['TmuxBackend']
