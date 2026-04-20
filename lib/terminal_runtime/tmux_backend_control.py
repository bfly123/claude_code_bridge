from __future__ import annotations

from terminal_runtime.tmux_respawn_service import TmuxRespawnService
from terminal_runtime.tmux_send import TmuxTextSender
from terminal_runtime.tmux_backend_runtime import (
    activate as _activate_impl,
    is_alive as _is_alive_impl,
    kill_pane as _kill_pane_impl,
    save_crash_log as _save_crash_log_impl,
    send_key as _send_key_impl,
)


class TmuxBackendControlMixin:
    def send_text_to_pane(self, pane_id: str, text: str) -> None:
        pane_id = self._require_pane_id(pane_id, action='send_text_to_pane')
        self.send_text(pane_id, text)

    def is_tmux_pane_alive(self, pane_id: str) -> bool:
        pane_id = self._require_pane_id(pane_id, action='is_tmux_pane_alive')
        return self.is_pane_alive(pane_id)

    def kill_tmux_pane(self, pane_id: str) -> None:
        pane_id = self._require_pane_id(pane_id, action='kill_tmux_pane')
        self._tmux_run(['kill-pane', '-t', pane_id], check=False)

    def send_text(self, pane_id: str, text: str) -> None:
        self._services.text_sender.send_text(pane_id, text)

    def _text_sender(self) -> TmuxTextSender:
        return self._services.text_sender

    def send_key(self, pane_id: str, key: str) -> bool:
        return _send_key_impl(self, pane_id, key)

    def is_alive(self, pane_id: str) -> bool:
        return _is_alive_impl(self, pane_id)

    def kill_pane(self, pane_id: str) -> None:
        _kill_pane_impl(self, pane_id)

    def activate(self, pane_id: str) -> None:
        _activate_impl(self, pane_id)

    def respawn_pane(
        self,
        pane_id: str,
        *,
        cmd: str,
        cwd: str | None = None,
        stderr_log_path: str | None = None,
        remain_on_exit: bool = True,
    ) -> None:
        self._services.respawn_service.respawn_pane(
            pane_id,
            cmd=cmd,
            cwd=cwd,
            stderr_log_path=stderr_log_path,
            remain_on_exit=remain_on_exit,
        )

    def _respawn_service(self) -> TmuxRespawnService:
        return self._services.respawn_service

    def save_crash_log(
        self,
        pane_id: str,
        crash_log_path: str,
        *,
        lines: int = 1000,
    ) -> None:
        _save_crash_log_impl(self, pane_id, crash_log_path, lines=lines)


__all__ = ['TmuxBackendControlMixin']
