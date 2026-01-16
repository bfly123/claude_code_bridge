from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from ccb_config import apply_backend_env
from project_id import compute_ccb_project_id
from session_utils import find_project_session_file as _find_project_session_file, safe_write_session
from terminal import get_backend_for_session

apply_backend_env()


def find_project_session_file(work_dir: Path) -> Optional[Path]:
    return _find_project_session_file(work_dir, ".opencode-session")


def _read_json(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8-sig")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class OpenCodeProjectSession:
    session_file: Path
    data: dict

    @property
    def session_id(self) -> str:
        # Legacy/compat: CCB's launcher writes its own session id under "session_id".
        # OpenCode itself uses a different "ses_..." id in its storage; that's stored separately
        # under "opencode_session_id" (see `opencode_session_id` property).
        return str(self.data.get("ccb_session_id") or self.data.get("session_id") or "").strip()

    @property
    def ccb_session_id(self) -> str:
        return self.session_id

    @property
    def terminal(self) -> str:
        return (self.data.get("terminal") or "tmux").strip() or "tmux"

    @property
    def pane_id(self) -> str:
        v = self.data.get("pane_id")
        if not v and self.terminal == "tmux":
            v = self.data.get("tmux_session")
        return str(v or "").strip()

    @property
    def pane_title_marker(self) -> str:
        return str(self.data.get("pane_title_marker") or "").strip()

    @property
    def opencode_session_id(self) -> str:
        # OpenCode internal session id in storage, typically "ses_<...>".
        # Backwards compatible: if older session files stored it under "session_id", accept that too.
        sid = str(self.data.get("opencode_session_id") or self.data.get("opencode_storage_session_id") or "").strip()
        if sid:
            return sid
        legacy = str(self.data.get("session_id") or "").strip()
        if legacy.startswith("ses_"):
            return legacy
        return ""

    @property
    def opencode_session_id_filter(self) -> str | None:
        sid = self.opencode_session_id
        if sid and sid.startswith("ses_"):
            return sid
        return None

    @property
    def opencode_project_id(self) -> str:
        return str(self.data.get("opencode_project_id") or "").strip()

    @property
    def work_dir(self) -> str:
        return str(self.data.get("work_dir") or self.session_file.parent)

    @property
    def runtime_dir(self) -> Path:
        return Path(self.data.get("runtime_dir") or self.session_file.parent)

    @property
    def start_cmd(self) -> str:
        return str(self.data.get("start_cmd") or "").strip()

    def backend(self):
        return get_backend_for_session(self.data)

    def ensure_pane(self) -> Tuple[bool, str]:
        backend = self.backend()
        if not backend:
            return False, "Terminal backend not available"

        pane_id = self.pane_id
        if pane_id and backend.is_alive(pane_id):
            return True, pane_id

        marker = self.pane_title_marker
        resolver = getattr(backend, "find_pane_by_title_marker", None)
        if marker and callable(resolver):
            resolved = resolver(marker)
            if resolved and backend.is_alive(str(resolved)):
                self.data["pane_id"] = str(resolved)
                self.data["updated_at"] = _now_str()
                self._write_back()
                return True, str(resolved)

        if self.terminal == "tmux":
            start_cmd = self.start_cmd
            respawn = getattr(backend, "respawn_pane", None)
            if start_cmd and callable(respawn):
                last_err: str | None = None
                target = pane_id
                if marker and callable(resolver):
                    try:
                        target = resolver(marker) or target
                    except Exception:
                        pass
                if target and str(target).startswith("%"):
                    try:
                        saver = getattr(backend, "save_crash_log", None)
                        if callable(saver):
                            try:
                                runtime = self.runtime_dir
                                runtime.mkdir(parents=True, exist_ok=True)
                                crash_log = runtime / f"pane-crash-{int(time.time())}.log"
                                saver(str(target), str(crash_log), lines=1000)
                            except Exception:
                                pass
                        respawn(str(target), cmd=start_cmd, cwd=self.work_dir, remain_on_exit=True)
                        if backend.is_alive(str(target)):
                            self.data["pane_id"] = str(target)
                            self.data["updated_at"] = _now_str()
                            self._write_back()
                            return True, str(target)
                        last_err = "respawn did not revive pane"
                    except Exception as exc:
                        last_err = f"{exc}"
                if last_err:
                    return False, f"Pane not alive and respawn failed: {last_err}"

        return False, f"Pane not alive: {pane_id}"

    def update_opencode_binding(self, *, session_id: Optional[str], project_id: Optional[str]) -> None:
        updated = False
        if session_id and self.data.get("opencode_session_id") != session_id:
            self.data["opencode_session_id"] = session_id
            updated = True
        if project_id and self.data.get("opencode_project_id") != project_id:
            self.data["opencode_project_id"] = project_id
            updated = True
        if updated:
            self.data["updated_at"] = _now_str()
            if self.data.get("active") is False:
                self.data["active"] = True
            self._write_back()

    def _write_back(self) -> None:
        payload = json.dumps(self.data, ensure_ascii=False, indent=2) + "\n"
        ok, _err = safe_write_session(self.session_file, payload)
        if not ok:
            # Best-effort: never raise (daemon should continue).
            return


def load_project_session(work_dir: Path) -> Optional[OpenCodeProjectSession]:
    session_file = find_project_session_file(work_dir)
    if not session_file:
        return None
    data = _read_json(session_file)
    if not data:
        return None
    return OpenCodeProjectSession(session_file=session_file, data=data)


def compute_session_key(session: OpenCodeProjectSession) -> str:
    """
    Compute the daemon routing/serialization key for this provider.

    Hard rule: include provider + ccb_project_id to isolate projects and providers.
    """
    pid = str(session.data.get("ccb_project_id") or "").strip()
    if not pid:
        try:
            pid = compute_ccb_project_id(Path(session.work_dir))
        except Exception:
            pid = ""
    return f"opencode:{pid}" if pid else "opencode:unknown"
