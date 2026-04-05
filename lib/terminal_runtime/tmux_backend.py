from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import time
from typing import Optional

from terminal_runtime.backend_types import TerminalBackend
from terminal_runtime.env import subprocess_kwargs as _subprocess_kwargs_impl
from terminal_runtime.tmux import looks_like_pane_id as _looks_like_pane_id_impl
from terminal_runtime.tmux import looks_like_tmux_target as _looks_like_tmux_target_impl
from terminal_runtime.tmux import tmux_base as _tmux_base_impl
from terminal_runtime.tmux_logs import TmuxPaneLogManager
from terminal_runtime.tmux_panes import TmuxPaneService
from terminal_runtime.tmux_respawn_service import TmuxRespawnService
from terminal_runtime.tmux_send import TmuxTextSender
from terminal_runtime.tmux_backend_runtime import (
    TmuxBackendServices,
    activate as _activate_impl,
    activate_tmux_pane as _activate_tmux_pane_impl,
    build_backend_services as _build_backend_services_impl,
    create_pane as _create_pane_impl,
    ensure_not_in_copy_mode as _ensure_not_in_copy_mode_impl,
    is_alive as _is_alive_impl,
    kill_pane as _kill_pane_impl,
    save_crash_log as _save_crash_log_impl,
    send_key as _send_key_impl,
)


def _subprocess_kwargs() -> dict:
    return _subprocess_kwargs_impl()


def _run(*args, **kwargs):
    kwargs.update(_subprocess_kwargs())
    import subprocess as _sp

    return _sp.run(*args, **kwargs)
class TmuxBackend(TerminalBackend):
    _ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

    def __init__(self, *, socket_name: str | None = None, socket_path: str | None = None):
        self._socket_path = (socket_path or os.environ.get("CCB_TMUX_SOCKET_PATH") or "").strip() or None
        if self._socket_path:
            self._socket_path = str(Path(self._socket_path).expanduser())
        self._socket_name = (socket_name or os.environ.get("CCB_TMUX_SOCKET") or "").strip() or None
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
                    "capture_output": True,
                    "text": True,
                    "encoding": "utf-8",
                    "errors": "replace",
                }
            )
        if input_bytes is not None:
            kwargs["input"] = input_bytes
        if timeout is not None:
            kwargs["timeout"] = timeout
        return _run([*self._tmux_base(), *args], check=check, **kwargs)

    def pane_log_path(self, pane_id: str) -> Optional[Path]:
        return self._services.pane_log_manager.pane_log_path(pane_id)

    def ensure_pane_log(self, pane_id: str) -> Optional[Path]:
        return self._services.pane_log_manager.ensure_pane_log(pane_id)

    def refresh_pane_logs(self) -> None:
        self._services.pane_log_manager.refresh_pane_logs()

    def _pane_log_manager(self) -> TmuxPaneLogManager:
        return self._services.pane_log_manager

    @staticmethod
    def _looks_like_pane_id(value: str) -> bool:
        return _looks_like_pane_id_impl(value)

    def _require_pane_id(self, pane_id: str, *, action: str) -> str:
        pane_id = (pane_id or "").strip()
        if not self._looks_like_pane_id(pane_id):
            raise ValueError(f"{action} requires tmux pane id, got {pane_id!r}")
        return pane_id

    def pane_exists(self, pane_id: str) -> bool:
        return self._services.pane_service.pane_exists(pane_id)

    @staticmethod
    def _looks_like_tmux_target(value: str) -> bool:
        return _looks_like_tmux_target_impl(value)

    def get_current_pane_id(self) -> str:
        return self._services.pane_service.get_current_pane_id(env_pane=os.environ.get("TMUX_PANE", ""))

    def split_pane(self, parent_pane_id: str, direction: str, percent: int) -> str:
        return self._services.pane_service.split_pane(parent_pane_id, direction=direction, percent=percent)

    def set_pane_title(self, pane_id: str, title: str) -> None:
        self._services.pane_service.set_pane_title(pane_id, title)

    def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
        self._services.pane_service.set_pane_user_option(pane_id, name, value)

    def set_pane_style(
        self,
        pane_id: str,
        *,
        border_style: str | None = None,
        active_border_style: str | None = None,
    ) -> None:
        self._services.pane_service.set_pane_style(
            pane_id,
            border_style=border_style,
            active_border_style=active_border_style,
        )

    def find_pane_by_title_marker(self, marker: str) -> Optional[str]:
        return self._services.pane_service.find_pane_by_title_marker(marker)

    def find_pane_by_user_options(self, expected: dict[str, str]) -> Optional[str]:
        return self._services.pane_service.find_pane_by_user_options(expected)

    def list_panes_by_user_options(self, expected: dict[str, str]) -> list[str]:
        return self._services.pane_service.list_panes_by_user_options(expected)

    def describe_pane(self, pane_id: str, *, user_options: tuple[str, ...] = ()) -> dict[str, str] | None:
        return self._services.pane_service.describe_pane(pane_id, user_options=user_options)

    def get_pane_content(self, pane_id: str, lines: int = 20) -> Optional[str]:
        return self._services.pane_service.get_pane_content(pane_id, lines=lines)

    def get_text(self, pane_id: str, lines: int = 20) -> Optional[str]:
        return self.get_pane_content(pane_id, lines=lines)

    def is_pane_alive(self, pane_id: str) -> bool:
        return self._services.pane_service.is_pane_alive(pane_id)

    def send_text_to_pane(self, pane_id: str, text: str) -> None:
        pane_id = self._require_pane_id(pane_id, action="send_text_to_pane")
        self.send_text(pane_id, text)

    def is_tmux_pane_alive(self, pane_id: str) -> bool:
        pane_id = self._require_pane_id(pane_id, action="is_tmux_pane_alive")
        return self.is_pane_alive(pane_id)

    def kill_tmux_pane(self, pane_id: str) -> None:
        pane_id = self._require_pane_id(pane_id, action="kill_tmux_pane")
        self._tmux_run(["kill-pane", "-t", pane_id], check=False)

    def activate_tmux_pane(self, pane_id: str) -> None:
        _activate_tmux_pane_impl(self, pane_id)

    def _ensure_not_in_copy_mode(self, pane_id: str) -> None:
        _ensure_not_in_copy_mode_impl(self, pane_id)

    def send_text(self, pane_id: str, text: str) -> None:
        self._services.text_sender.send_text(pane_id, text)

    def _text_sender(self) -> TmuxTextSender:
        return self._services.text_sender

    def _pane_service(self) -> TmuxPaneService:
        return self._services.pane_service

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

    def save_crash_log(self, pane_id: str, crash_log_path: str, *, lines: int = 1000) -> None:
        _save_crash_log_impl(self, pane_id, crash_log_path, lines=lines)

    def create_pane(
        self,
        cmd: str,
        cwd: str,
        direction: str = "right",
        percent: int = 50,
        parent_pane: Optional[str] = None,
    ) -> str:
        return _create_pane_impl(
            self,
            cmd=cmd,
            cwd=cwd,
            direction=direction,
            percent=percent,
            parent_pane=parent_pane,
        )
