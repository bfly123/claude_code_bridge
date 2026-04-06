from __future__ import annotations

from dataclasses import dataclass

from provider_backends.pane_log_support.session import PaneLogProjectSessionBase

from .binding import update_opencode_binding as _update_opencode_binding_impl


@dataclass
class OpenCodeProjectSession(PaneLogProjectSessionBase):
    @property
    def ccb_session_id(self) -> str:
        return str(self.data.get("ccb_session_id") or "").strip()

    @property
    def opencode_session_id(self) -> str:
        return str(
            self.data.get("opencode_session_id")
            or self.data.get("opencode_storage_session_id")
            or ""
        ).strip()

    @property
    def opencode_session_id_filter(self) -> str | None:
        session_id = self.opencode_session_id
        if session_id and session_id.startswith("ses_"):
            return session_id
        return None

    @property
    def opencode_project_id(self) -> str:
        return str(self.data.get("opencode_project_id") or "").strip()

    def backend(self):
        from provider_backends.opencode import session as session_module

        return session_module.get_backend_for_session(self.data)

    def update_opencode_binding(self, *, session_id: str | None, project_id: str | None) -> None:
        _update_opencode_binding_impl(self, session_id=session_id, project_id=project_id)


__all__ = ["OpenCodeProjectSession"]
