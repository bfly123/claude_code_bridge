from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from terminal_runtime.backend_env import apply_backend_env
from provider_core.runtime_specs import provider_marker_prefix
from terminal_runtime import get_backend_for_session, get_pane_id_from_session

from .comm_runtime import (
    DROID_SESSIONS_ROOT,
    DroidLogReader,
    ensure_droid_watchdog_started,
    find_droid_session_file,
    handle_droid_session_event,
    load_droid_session_info,
    publish_droid_registry,
    read_droid_session_start,
    remember_droid_session_binding,
)
from .session import find_project_session_file as find_droid_project_session_file

apply_backend_env()


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

        self._log_reader: Optional[DroidLogReader] = None
        self._log_reader_primed = False

        self._publish_registry()

        if not lazy_init:
            self._ensure_log_reader()
            healthy, msg = self._check_session_health()
            if not healthy:
                raise RuntimeError(f"❌ Session unhealthy: {msg}\nHint: run ccb droid (or add droid to ccb.config) to start a new session")

    @property
    def log_reader(self) -> DroidLogReader:
        if self._log_reader is None:
            self._ensure_log_reader()
        return self._log_reader

    def _ensure_log_reader(self) -> None:
        if self._log_reader is not None:
            return
        work_dir_hint = self.session_info.get("work_dir")
        log_work_dir = Path(work_dir_hint) if isinstance(work_dir_hint, str) and work_dir_hint else None
        self._log_reader = DroidLogReader(work_dir=log_work_dir)
        preferred_session = self.session_info.get("droid_session_path")
        if preferred_session:
            self._log_reader.set_preferred_session(Path(str(preferred_session)))
        session_id = self.session_info.get("droid_session_id")
        if session_id:
            self._log_reader.set_session_id_hint(session_id)
        if not self._log_reader_primed:
            self._prime_log_binding()
            self._log_reader_primed = True

    def _find_session_file(self) -> Optional[Path]:
        return find_droid_session_file(Path.cwd())

    def _load_session_info(self) -> Optional[dict]:
        return load_droid_session_info(self._find_session_file())

    def _prime_log_binding(self) -> None:
        session_path = self.log_reader.current_session_path()
        if not session_path:
            return
        self._remember_droid_session(session_path)

    def _publish_registry(self) -> None:
        publish_droid_registry(
            session_info=self.session_info,
            ccb_session_id=self.ccb_session_id,
            terminal=self.terminal,
            pane_id=self.pane_id,
            project_session_file=self.project_session_file,
        )

    def _check_session_health(self) -> Tuple[bool, str]:
        return self._check_session_health_impl(probe_terminal=True)

    def _check_session_health_impl(self, probe_terminal: bool) -> Tuple[bool, str]:
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
        data = remember_droid_session_binding(
            project_session_file=path,
            session_path=session_path,
            session_id_loader=read_droid_session_start,
        )
        if not data:
            return
        publish_droid_registry(
            session_info=data,
            ccb_session_id=self.ccb_session_id,
            terminal=self.terminal,
            pane_id=self.pane_id,
            project_session_file=str(path),
        )

    def ping(self, display: bool = True) -> Tuple[bool, str]:
        healthy, status = self._check_session_health()
        msg = f"✅ Droid connection OK ({status})" if healthy else f"❌ Droid connection error: {status}"
        if display:
            print(msg)
        return healthy, msg

    def get_status(self) -> Dict[str, Any]:
        healthy, status = self._check_session_health()
        return {
            "ccb_session_id": self.ccb_session_id,
            "terminal": self.terminal,
            "pane_id": self.pane_id,
            "healthy": healthy,
            "status": status,
        }


def _load_project_session(work_dir: Path):
    from .session import load_project_session

    return load_project_session(work_dir)


def _handle_droid_session_event(path: Path) -> None:
    handle_droid_session_event(
        path,
        find_project_session_file_fn=find_droid_project_session_file,
        load_project_session_fn=_load_project_session,
    )


def _ensure_droid_watchdog_started() -> None:
    ensure_droid_watchdog_started(
        root=DROID_SESSIONS_ROOT,
        find_project_session_file_fn=find_droid_project_session_file,
        load_project_session_fn=_load_project_session,
    )


_ensure_droid_watchdog_started()


__all__ = [
    'DROID_SESSIONS_ROOT',
    'DroidCommunicator',
    'DroidLogReader',
    'find_droid_project_session_file',
    'read_droid_session_start',
]
