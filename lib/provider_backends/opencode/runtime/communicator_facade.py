from __future__ import annotations

import os
import time
from pathlib import Path

from opencode_runtime.paths import OPENCODE_STORAGE_ROOT
from pane_registry_runtime import upsert_registry
from terminal_runtime import get_backend_for_session, get_pane_id_from_session

from ..session import find_project_session_file as find_opencode_project_session_file
from . import (
    ask_async as _ask_async_impl,
    ask_sync as _ask_sync_impl,
    check_session_health as _check_session_health_impl,
    find_opencode_session_file,
    initialize_state as _initialize_comm_state,
    load_opencode_session_info,
    ping as _ping_impl,
    publish_opencode_registry,
    send_message as _send_message_impl,
)
from .log_reader_facade import OpenCodeLogReader


class OpenCodeCommunicator:
    def __init__(self, lazy_init: bool = False):
        _initialize_comm_state(
            self,
            get_backend_for_session_fn=get_backend_for_session,
            get_pane_id_from_session_fn=get_pane_id_from_session,
            log_reader_cls=OpenCodeLogReader,
            publish_registry_fn=lambda **kwargs: publish_opencode_registry(
                upsert_registry_fn=upsert_registry,
                **kwargs,
            ),
        )

        if not lazy_init:
            healthy, msg = self._check_session_health()
            if not healthy:
                raise RuntimeError(
                    f"❌ Session unhealthy: {msg}\nTip: Add opencode to ccb.config and run `ccb` to start a new session"
                )

    def _find_session_file(self) -> Path | None:
        return find_opencode_session_file(cwd=Path.cwd(), finder=find_opencode_project_session_file)

    def _load_session_info(self) -> dict | None:
        return load_opencode_session_info(session_finder=self._find_session_file)

    def _check_session_health(self) -> tuple[bool, str]:
        return self._check_session_health_impl(probe_terminal=True)

    def _check_session_health_impl(self, probe_terminal: bool) -> tuple[bool, str]:
        return _check_session_health_impl(self, probe_terminal=probe_terminal, storage_root=OPENCODE_STORAGE_ROOT)

    def ping(self, display: bool = True) -> tuple[bool, str]:
        return _ping_impl(self, display=display)

    def _send_via_terminal(self, content: str) -> None:
        if not self.backend or not self.pane_id:
            raise RuntimeError("Terminal session not configured")
        self.backend.send_text(self.pane_id, content)

    def _send_message(self, content: str) -> tuple[str, dict[str, object]]:
        return _send_message_impl(self, content)

    def _generate_marker(self) -> str:
        return f"{self.marker_prefix}-{int(time.time())}-{os.getpid()}"

    def ask_async(self, question: str) -> bool:
        return _ask_async_impl(self, question)

    def ask_sync(self, question: str, timeout: int | None = None) -> str | None:
        return _ask_sync_impl(self, question, timeout=timeout)


__all__ = ["OpenCodeCommunicator"]
