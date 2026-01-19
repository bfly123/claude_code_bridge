from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from ccb_config import apply_backend_env
from claude_session_resolver import resolve_claude_session
from project_id import compute_ccb_project_id
from session_utils import safe_write_session
from terminal import get_backend_for_session

apply_backend_env()


def _now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class ClaudeProjectSession:
    session_file: Path
    data: dict
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
    def claude_session_id(self) -> str:
        return str(self.data.get("claude_session_id") or self.data.get("session_id") or "").strip()

    @property
    def claude_session_path(self) -> str:
        return str(self.data.get("claude_session_path") or "").strip()

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
            if resolved and backend.is_alive(str(resolved)):
                self.data["pane_id"] = str(resolved)
                self.data["updated_at"] = _now_str()
                self._write_back()
                return True, str(resolved)

        return False, f"Pane not alive: {pane_id}"

    def update_claude_binding(self, *, session_path: Optional[Path], session_id: Optional[str]) -> None:
        updated = False
        if session_path:
            try:
                session_path_str = str(Path(session_path).expanduser())
            except Exception:
                session_path_str = str(session_path)
            if session_path_str and self.data.get("claude_session_path") != session_path_str:
                self.data["claude_session_path"] = session_path_str
                updated = True

        if session_id and self.data.get("claude_session_id") != session_id:
            self.data["claude_session_id"] = session_id
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
            return


def load_project_session(work_dir: Path) -> Optional[ClaudeProjectSession]:
    resolution = resolve_claude_session(work_dir)
    if not resolution:
        return None
    data = dict(resolution.data or {})
    if not data:
        return None
    data.setdefault("work_dir", str(work_dir))
    if not data.get("ccb_project_id"):
        try:
            data["ccb_project_id"] = compute_ccb_project_id(Path(data.get("work_dir") or work_dir))
        except Exception:
            pass
    session_file = resolution.session_file
    if not session_file:
        try:
            from session_utils import project_config_dir

            session_file = project_config_dir(work_dir) / ".claude-session"
        except Exception:
            session_file = None
    if not session_file:
        return None
    return ClaudeProjectSession(session_file=session_file, data=data)


def compute_session_key(session: ClaudeProjectSession) -> str:
    pid = str(session.data.get("ccb_project_id") or "").strip()
    if not pid:
        try:
            pid = compute_ccb_project_id(Path(session.work_dir))
        except Exception:
            pid = ""
    return f"claude:{pid}" if pid else "claude:unknown"
