from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from ccb_config import apply_backend_env
from claude_session_resolver import resolve_claude_session
from env_utils import env_bool, env_int
from project_id import compute_ccb_project_id, normalize_work_dir
from session_utils import safe_write_session
from terminal import get_backend_for_session

apply_backend_env()

_AUTO_TRANSFER_LOCK = threading.Lock()
_AUTO_TRANSFER_SEEN: dict[str, float] = {}


def _auto_transfer_key(work_dir: Path, session_path: Path) -> str:
    return f"{work_dir}::{session_path}"


def _maybe_auto_extract_old_session(old_session_path: str, work_dir: Path) -> None:
    if not env_bool("CCB_CTX_TRANSFER_ON_SESSION_SWITCH", True):
        return
    if not old_session_path:
        return
    try:
        path = Path(old_session_path).expanduser()
    except Exception:
        return
    if not path.exists():
        return
    try:
        work_dir = Path(work_dir).expanduser()
    except Exception:
        return

    key = _auto_transfer_key(work_dir, path)
    now = time.time()
    with _AUTO_TRANSFER_LOCK:
        if key in _AUTO_TRANSFER_SEEN:
            return
        # prune stale keys (1h)
        for k, ts in list(_AUTO_TRANSFER_SEEN.items()):
            if now - ts > 3600:
                _AUTO_TRANSFER_SEEN.pop(k, None)
        _AUTO_TRANSFER_SEEN[key] = now

    def _run() -> None:
        try:
            from memory import ContextTransfer
        except Exception:
            return
        try:
            last_n = env_int("CCB_CTX_TRANSFER_LAST_N", 0)
            max_tokens = env_int("CCB_CTX_TRANSFER_MAX_TOKENS", 8000)
            fmt = (os.environ.get("CCB_CTX_TRANSFER_FORMAT") or "markdown").strip().lower() or "markdown"
            provider = (os.environ.get("CCB_CTX_TRANSFER_PROVIDER") or "auto").strip().lower() or "auto"
        except Exception:
            last_n = 3
            max_tokens = 8000
            fmt = "markdown"
            provider = "auto"
        try:
            transfer = ContextTransfer(max_tokens=max_tokens, work_dir=work_dir)
            context = transfer.extract_conversations(session_path=path, last_n=last_n)
            if not context.conversations:
                return
            ts = time.strftime("%Y%m%d-%H%M%S")
            filename = f"claude-{ts}-{path.stem}"
            transfer.save_transfer(context, fmt, provider, filename=filename)
        except Exception:
            return

    threading.Thread(target=_run, daemon=True).start()


def _now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _infer_work_dir_from_session_file(session_file: Path) -> Path:
    try:
        parent = Path(session_file).parent
    except Exception:
        return Path.cwd()
    if parent.name in (".ccb", ".ccb_config"):
        return parent.parent
    return parent


def _ensure_work_dir_fields(data: dict, *, session_file: Path, fallback_work_dir: Optional[Path] = None) -> None:
    if not isinstance(data, dict):
        return

    work_dir_raw = data.get("work_dir")
    work_dir = work_dir_raw.strip() if isinstance(work_dir_raw, str) else ""
    if not work_dir:
        base = fallback_work_dir or _infer_work_dir_from_session_file(session_file)
        work_dir = str(base)
        data["work_dir"] = work_dir

    work_dir_norm_raw = data.get("work_dir_norm")
    work_dir_norm = work_dir_norm_raw.strip() if isinstance(work_dir_norm_raw, str) else ""
    if not work_dir_norm:
        try:
            data["work_dir_norm"] = normalize_work_dir(work_dir)
        except Exception:
            data["work_dir_norm"] = work_dir

    if not str(data.get("ccb_project_id") or "").strip():
        try:
            data["ccb_project_id"] = compute_ccb_project_id(Path(work_dir))
        except Exception:
            pass


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

    def _attach_pane_log(self, backend: object, pane_id: str) -> None:
        ensure = getattr(backend, "ensure_pane_log", None)
        if callable(ensure):
            try:
                ensure(str(pane_id))
            except Exception:
                pass

    def ensure_pane(self) -> Tuple[bool, str]:
        backend = self.backend()
        if not backend:
            return False, "Terminal backend not available"

        pane_id = self.pane_id
        marker = self.pane_title_marker
        resolver = getattr(backend, "find_pane_by_title_marker", None)
        marker_lookup_attempted = bool(marker and callable(resolver))
        marker_resolved_alive = False

        # Prefer marker-discovered pane to avoid routing to a stale but alive pane_id.
        if marker and callable(resolver):
            resolved = resolver(marker)
            if resolved and backend.is_alive(str(resolved)):
                marker_resolved_alive = True
                if str(resolved) != str(pane_id):
                    self.data["pane_id"] = str(resolved)
                    self.data["updated_at"] = _now_str()
                    self._write_back()
                self._attach_pane_log(backend, str(resolved))
                return True, str(resolved)

        if pane_id and backend.is_alive(pane_id):
            # If marker lookup failed to find a live pane, avoid routing to a stale/reused pane_id.
            if not (self.terminal == "tmux" and marker_lookup_attempted and not marker_resolved_alive):
                self._attach_pane_log(backend, pane_id)
                return True, pane_id

        if marker and callable(resolver):
            resolved = resolver(marker)
            if resolved and backend.is_alive(str(resolved)):
                self.data["pane_id"] = str(resolved)
                self.data["updated_at"] = _now_str()
                self._write_back()
                self._attach_pane_log(backend, str(resolved))
                return True, str(resolved)

        if marker_lookup_attempted and not marker_resolved_alive and pane_id:
            return False, f"Pane marker not found for active pane id: {pane_id}"

        return False, f"Pane not alive: {pane_id}"

    def update_claude_binding(self, *, session_path: Optional[Path], session_id: Optional[str]) -> None:
        old_path = str(self.data.get("claude_session_path") or "").strip()
        old_id = str(self.data.get("claude_session_id") or "").strip()
        updated = False
        session_path_str = ""
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
            new_id = str(session_id or "").strip()
            if not new_id and session_path_str:
                try:
                    new_id = Path(session_path_str).stem
                except Exception:
                    new_id = ""
            if old_id and old_id != new_id:
                self.data["old_claude_session_id"] = old_id
            if old_path and (old_path != session_path_str or (old_id and old_id != new_id)):
                self.data["old_claude_session_path"] = old_path
            if old_path or old_id:
                self.data["old_updated_at"] = _now_str()
            self.data["updated_at"] = _now_str()
            if self.data.get("active") is False:
                self.data["active"] = True
            self._write_back()
            changed = False
            if session_path_str:
                changed = old_path != session_path_str
            elif new_id:
                changed = new_id != old_id
            if changed and old_path:
                _maybe_auto_extract_old_session(old_path, Path(self.work_dir))

    def _write_back(self) -> None:
        _ensure_work_dir_fields(self.data, session_file=self.session_file)
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
    _ensure_work_dir_fields(data, session_file=session_file, fallback_work_dir=work_dir)
    return ClaudeProjectSession(session_file=session_file, data=data)


def compute_session_key(session: ClaudeProjectSession) -> str:
    pid = str(session.data.get("ccb_project_id") or "").strip()
    if not pid:
        try:
            pid = compute_ccb_project_id(Path(session.work_dir))
        except Exception:
            pid = ""
    return f"claude:{pid}" if pid else "claude:unknown"
