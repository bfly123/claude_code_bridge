from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from terminal_runtime import get_backend_for_session, get_pane_id_from_session

from ..session import find_project_session_file as find_gemini_project_session_file
from . import (
    ask_async as _ask_async_impl,
    ask_sync as _ask_sync_impl,
    check_session_health as _check_session_health_impl,
    consume_pending as _consume_pending_impl,
    ensure_log_reader as _ensure_log_reader_impl,
    find_gemini_session_file,
    get_status as _get_status_impl,
    initialize_state as _initialize_state,
    load_gemini_session_info,
    prime_log_binding as _prime_log_binding_impl,
    publish_initial_registry_binding as _publish_initial_registry_binding_impl,
    remember_gemini_session as _remember_gemini_session_impl,
    send_message as _send_message_impl,
    update_project_session_binding,
)
from .log_reader_facade import GeminiLogReader


def _publish_registry_binding_proxy(**kwargs) -> None:
    from .. import comm as gemini_comm_module

    gemini_comm_module.publish_registry_binding(**kwargs)


class GeminiCommunicator:
    """Communicate with Gemini via terminal and read replies from session files."""

    def __init__(self, lazy_init: bool = False):
        _initialize_state(
            self,
            get_pane_id_from_session_fn=get_pane_id_from_session,
            get_backend_for_session_fn=get_backend_for_session,
        )
        _publish_initial_registry_binding_impl(
            self,
            publish_registry_binding_fn=_publish_registry_binding_proxy,
        )

        if not lazy_init:
            self._ensure_log_reader()
            healthy, msg = self._check_session_health()
            if not healthy:
                raise RuntimeError(
                    f"❌ Session unhealthy: {msg}\nHint: Please run ccb gemini (or add gemini to ccb.config)"
                )

    @property
    def log_reader(self) -> GeminiLogReader:
        if self._log_reader is None:
            self._ensure_log_reader()
        return self._log_reader

    def _ensure_log_reader(self) -> None:
        _ensure_log_reader_impl(self, log_reader_cls=GeminiLogReader)

    def _find_session_file(self) -> Path | None:
        return find_gemini_session_file(cwd=Path.cwd(), finder=find_gemini_project_session_file)

    def _prime_log_binding(self) -> None:
        _prime_log_binding_impl(self)

    def _load_session_info(self):
        return load_gemini_session_info(session_finder=self._find_session_file)

    def _check_session_health(self) -> tuple[bool, str]:
        return self._check_session_health_impl(probe_terminal=True)

    def _check_session_health_impl(self, probe_terminal: bool) -> tuple[bool, str]:
        return _check_session_health_impl(self, probe_terminal=probe_terminal)

    def _send_via_terminal(self, content: str) -> bool:
        if not self.backend or not self.pane_id:
            raise RuntimeError("Terminal session not configured")
        self.backend.send_text(self.pane_id, content)
        return True

    def _send_message(self, content: str) -> tuple[str, dict[str, Any]]:
        return _send_message_impl(self, content)

    def _generate_marker(self) -> str:
        return f"{self.marker_prefix}-{int(time.time())}-{os.getpid()}"

    def ask_async(self, question: str) -> bool:
        return _ask_async_impl(self, question)

    def ask_sync(self, question: str, timeout: int | None = None) -> str | None:
        return _ask_sync_impl(self, question, timeout=timeout)

    def consume_pending(self, display: bool = True, n: int = 1):
        return _consume_pending_impl(self, display=display, n=n)

    def _remember_gemini_session(self, session_path: Path) -> None:
        _remember_gemini_session_impl(
            self,
            session_path,
            update_project_session_binding_fn=update_project_session_binding,
            publish_registry_binding_fn=_publish_registry_binding_proxy,
        )

    def ping(self, display: bool = True) -> tuple[bool, str]:
        healthy, status = self._check_session_health()
        msg = f"✅ Gemini connection OK ({status})" if healthy else f"❌ Gemini connection error: {status}"
        if display:
            print(msg)
        return healthy, msg

    def get_status(self) -> dict[str, Any]:
        return _get_status_impl(self)


__all__ = ["GeminiCommunicator"]
