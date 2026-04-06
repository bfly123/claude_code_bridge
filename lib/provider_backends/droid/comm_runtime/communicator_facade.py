from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from provider_core.runtime_specs import provider_marker_prefix
from terminal_runtime import get_backend_for_session, get_pane_id_from_session


def _droid_comm_module():
    from .. import comm as droid_comm_module

    return droid_comm_module


def _droid_log_reader_cls():
    return _droid_comm_module().DroidLogReader


def _publish_droid_registry_proxy(**kwargs) -> None:
    _droid_comm_module().publish_droid_registry(**kwargs)


def _remember_droid_session_binding_proxy(**kwargs):
    return _droid_comm_module().remember_droid_session_binding(**kwargs)


def _read_droid_session_start_proxy(session_path: Path):
    return _droid_comm_module().read_droid_session_start(session_path)


def _find_droid_session_file_proxy(cwd: Path):
    return _droid_comm_module().find_droid_session_file(cwd)


def _load_droid_session_info_proxy(project_session):
    return _droid_comm_module().load_droid_session_info(project_session)


class DroidCommunicator:
    """Communicate with Droid via terminal and read replies from session logs."""

    def __init__(self, lazy_init: bool = False):
        self.session_info = self._load_session_info()
        if not self.session_info:
            raise RuntimeError("❌ No active Droid session found. Run 'ccb droid' (or add droid to ccb.config) first")

        self.ccb_session_id = str(self.session_info.get("ccb_session_id") or "").strip()
        self.terminal = self.session_info.get("terminal", "tmux")
        self.pane_id = get_pane_id_from_session(self.session_info) or ""
        self.pane_title_marker = self.session_info.get("pane_title_marker") or ""
        self.backend = get_backend_for_session(self.session_info)
        self.timeout = int(os.environ.get("DROID_SYNC_TIMEOUT", os.environ.get("CCB_SYNC_TIMEOUT", "3600")))
        self.marker_prefix = provider_marker_prefix("droid")
        self.project_session_file = self.session_info.get("_session_file")

        self._log_reader = None
        self._log_reader_primed = False

        self._publish_registry()

        if not lazy_init:
            self._ensure_log_reader()
            healthy, msg = self._check_session_health()
            if not healthy:
                raise RuntimeError(
                    f"❌ Session unhealthy: {msg}\nHint: run ccb droid (or add droid to ccb.config) to start a new session"
                )

    @property
    def log_reader(self):
        if self._log_reader is None:
            self._ensure_log_reader()
        return self._log_reader

    def _ensure_log_reader(self) -> None:
        if self._log_reader is not None:
            return
        work_dir_hint = self.session_info.get("work_dir")
        log_work_dir = Path(work_dir_hint) if isinstance(work_dir_hint, str) and work_dir_hint else None
        self._log_reader = _droid_log_reader_cls()(work_dir=log_work_dir)
        preferred_session = self.session_info.get("droid_session_path")
        if preferred_session:
            self._log_reader.set_preferred_session(Path(str(preferred_session)))
        session_id = self.session_info.get("droid_session_id")
        if session_id:
            self._log_reader.set_session_id_hint(session_id)
        if not self._log_reader_primed:
            self._prime_log_binding()
            self._log_reader_primed = True

    def _find_session_file(self) -> Path | None:
        return _find_droid_session_file_proxy(Path.cwd())

    def _load_session_info(self):
        return _load_droid_session_info_proxy(self._find_session_file())

    def _prime_log_binding(self) -> None:
        session_path = self.log_reader.current_session_path()
        if not session_path:
            return
        self._remember_droid_session(session_path)

    def _publish_registry(self) -> None:
        _publish_droid_registry_proxy(
            session_info=self.session_info,
            ccb_session_id=self.ccb_session_id,
            terminal=self.terminal,
            pane_id=self.pane_id,
            project_session_file=self.project_session_file,
        )

    def _check_session_health(self):
        return self._check_session_health_impl(probe_terminal=True)

    def _check_session_health_impl(self, probe_terminal: bool):
        try:
            if not self.pane_id:
                return False, "Session pane id not found"
            if probe_terminal and self.backend:
                pane_alive = self.backend.is_alive(self.pane_id)
                if not pane_alive:
                    return False, f"{self.terminal} session {self.pane_id} not found"
            return True, "Session OK"
        except Exception as exc:
            return False, f"Check failed: {exc}"

    def _remember_droid_session(self, session_path: Path) -> None:
        if not self.project_session_file:
            return
        if not session_path or not isinstance(session_path, Path):
            return
        path = Path(self.project_session_file)
        data = _remember_droid_session_binding_proxy(
            project_session_file=path,
            session_path=session_path,
            session_id_loader=_read_droid_session_start_proxy,
        )
        if not data:
            return
        _publish_droid_registry_proxy(
            session_info=data,
            ccb_session_id=self.ccb_session_id,
            terminal=self.terminal,
            pane_id=self.pane_id,
            project_session_file=str(path),
        )

    def ping(self, display: bool = True):
        healthy, status = self._check_session_health()
        msg = f"✅ Droid connection OK ({status})" if healthy else f"❌ Droid connection error: {status}"
        if display:
            print(msg)
        return healthy, msg

    def get_status(self) -> dict[str, Any]:
        healthy, status = self._check_session_health()
        return {
            "ccb_session_id": self.ccb_session_id,
            "terminal": self.terminal,
            "pane_id": self.pane_id,
            "healthy": healthy,
            "status": status,
        }


__all__ = ["DroidCommunicator"]
