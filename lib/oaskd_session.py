from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from ccb_config import apply_backend_env
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
        # Current .opencode-session uses "session_id". Keep compatibility with older/alternate keys.
        return str(self.data.get("session_id") or self.data.get("opencode_session_id") or "").strip()

    @property
    def terminal(self) -> str:
        return (self.data.get("terminal") or "tmux").strip() or "tmux"

    @property
    def pane_id(self) -> str:
        v = self.data.get("pane_id") if self.terminal in ("wezterm", "iterm2") else self.data.get("tmux_session")
        return str(v or "").strip()

    @property
    def pane_title_marker(self) -> str:
        return str(self.data.get("pane_title_marker") or "").strip()

    @property
    def opencode_session_id(self) -> str:
        # Backwards-compatible alias.
        return self.session_id

    @property
    def opencode_project_id(self) -> str:
        return str(self.data.get("opencode_project_id") or "").strip()

    @property
    def work_dir(self) -> str:
        return str(self.data.get("work_dir") or self.session_file.parent)

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
            if resolved:
                self.data["pane_id"] = str(resolved)
                self.data["updated_at"] = _now_str()
                self._write_back()
                return True, str(resolved)

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
    marker = session.pane_title_marker
    if marker:
        return f"opencode_marker:{marker}"
    pane = session.pane_id
    if pane:
        return f"opencode_pane:{pane}"
    sid = session.session_id
    if sid:
        return f"opencode:{sid}"
    return f"opencode_file:{session.session_file}"
