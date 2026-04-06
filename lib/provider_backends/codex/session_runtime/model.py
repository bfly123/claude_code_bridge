from __future__ import annotations

from dataclasses import dataclass

from provider_backends.pane_log_support.session import PaneLogProjectSessionBase

from ..start_cmd import effective_start_cmd
from .binding import update_codex_log_binding as _update_codex_log_binding_impl


@dataclass
class CodexProjectSession(PaneLogProjectSessionBase):
    @property
    def codex_session_path(self) -> str:
        return str(self.data.get("codex_session_path") or "").strip()

    @property
    def codex_session_id(self) -> str:
        return str(self.data.get("codex_session_id") or "").strip()

    @property
    def start_cmd(self) -> str:
        return effective_start_cmd(self.data)

    def backend(self):
        from provider_backends.codex import session as session_module

        return session_module.get_backend_for_session(self.data)

    def update_codex_log_binding(self, *, log_path: str | None, session_id: str | None) -> None:
        _update_codex_log_binding_impl(self, log_path=log_path, session_id=session_id)


__all__ = ["CodexProjectSession"]
