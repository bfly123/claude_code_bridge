from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from provider_backends.pane_log_support.session import PaneLogProjectSessionBase

from .binding import update_gemini_binding as _update_gemini_binding_impl


@dataclass
class GeminiProjectSession(PaneLogProjectSessionBase):
    @property
    def gemini_session_id(self) -> str:
        return str(self.data.get("gemini_session_id") or "").strip()

    @property
    def gemini_session_path(self) -> str:
        return str(self.data.get("gemini_session_path") or "").strip()

    def backend(self):
        from provider_backends.gemini import session as session_module

        return session_module.get_backend_for_session(self.data)

    def update_gemini_binding(self, *, session_path: Path | None, session_id: str | None) -> None:
        _update_gemini_binding_impl(self, session_path=session_path, session_id=session_id)


__all__ = ["GeminiProjectSession"]
