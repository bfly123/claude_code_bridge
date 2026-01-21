"""
OpenCode communication module

Reads replies from OpenCode storage (~/.local/share/opencode/storage) and sends messages by
injecting text into the OpenCode TUI pane via the configured terminal backend.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ccb_protocol import REQ_ID_PREFIX
from ccb_config import apply_backend_env
from i18n import t
from terminal import get_backend_for_session, get_pane_id_from_session
from session_utils import find_project_session_file, safe_write_session
from pane_registry import upsert_registry
from project_id import compute_ccb_project_id

apply_backend_env()

_REQ_ID_RE = re.compile(rf"{re.escape(REQ_ID_PREFIX)}\s*([0-9a-fA-F]{{32}})")


def compute_opencode_project_id(work_dir: Path) -> str:
    """
    Compute OpenCode projectID for a directory.

    OpenCode's current behavior (for git worktrees) uses the lexicographically smallest
    root commit hash from `git rev-list --max-parents=0 --all` as the projectID.
    Non-git directories fall back to "global".
    """
    try:
        cwd = Path(work_dir).expanduser()
    except Exception:
        cwd = Path.cwd()

    def _find_git_dir(start: Path) -> tuple[Path | None, Path | None]:
        """
        Return (git_root_dir, git_dir_path) if a .git entry is found.

        Handles:
        - normal repos: <root>/.git/ (directory)
        - worktrees: <worktree>/.git (file containing "gitdir: <path>")
        """
        for candidate in [start, *start.parents]:
            git_entry = candidate / ".git"
            if not git_entry.exists():
                continue
            if git_entry.is_dir():
                return candidate, git_entry
            if git_entry.is_file():
                try:
                    raw = git_entry.read_text(encoding="utf-8", errors="replace").strip()
                    prefix = "gitdir:"
                    if raw.lower().startswith(prefix):
                        gitdir = raw[len(prefix) :].strip()
                        gitdir_path = Path(gitdir)
                        if not gitdir_path.is_absolute():
                            gitdir_path = (candidate / gitdir_path).resolve()
                        return candidate, gitdir_path
                except Exception:
                    continue
        return None, None

    def _read_cached_project_id(git_dir: Path | None) -> str | None:
        if not git_dir:
            return None
        try:
            cache_path = git_dir / "opencode"
            if not cache_path.exists():
                return None
            cached = cache_path.read_text(encoding="utf-8", errors="replace").strip()
            return cached or None
        except Exception:
            return None

    git_root, git_dir = _find_git_dir(cwd)
    cached = _read_cached_project_id(git_dir)
    if cached:
        return cached

    try:
        import subprocess

        if not shutil.which("git"):
            return "global"

        kwargs = {
            "cwd": str(git_root or cwd),
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "stdout": subprocess.PIPE,
            "stderr": subprocess.DEVNULL,
            "check": False,
        }
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = startupinfo
        proc = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "--all"],
            **kwargs
        )
        roots = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
        roots.sort()
        return roots[0] if roots else "global"
    except Exception:
        return "global"


def _normalize_path_for_match(value: str) -> str:
    s = (value or "").strip()
    if os.name == "nt":
        # MSYS/Git-Bash style: /c/Users/... -> c:/Users/...
        if len(s) >= 4 and s[0] == "/" and s[2] == "/" and s[1].isalpha():
            s = f"{s[1].lower()}:/{s[3:]}"
        # WSL-style path string seen on Windows occasionally: /mnt/c/... -> c:/...
        m = re.match(r"^/mnt/([A-Za-z])/(.*)$", s)
        if m:
            s = f"{m.group(1).lower()}:/{m.group(2)}"

    try:
        path = Path(s).expanduser()
        # OpenCode "directory" seems to come from the launch cwd, so avoid resolve() to prevent
        # symlink/WSL mismatch (similar rationale to gemini hashing).
        normalized = str(path.absolute())
    except Exception:
        normalized = str(value)
    normalized = normalized.replace("\\", "/").rstrip("/")
    if os.name == "nt":
        normalized = normalized.lower()
    return normalized


def _path_is_same_or_parent(parent: str, child: str) -> bool:
    parent = _normalize_path_for_match(parent)
    child = _normalize_path_for_match(child)
    if parent == child:
        return True
    if not parent or not child:
        return False
    if not child.startswith(parent):
        return False
    # Ensure boundary on path segment
    return child == parent or child[len(parent) :].startswith("/")


def _env_truthy(name: str) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _path_matches(expected: str, actual: str, *, allow_parent: bool) -> bool:
    if allow_parent:
        return _path_is_same_or_parent(expected, actual)
    return _normalize_path_for_match(expected) == _normalize_path_for_match(actual)


def _is_wsl() -> bool:
    if os.environ.get("WSL_INTEROP") or os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return False


def _default_opencode_storage_root() -> Path:
    env = (os.environ.get("OPENCODE_STORAGE_ROOT") or "").strip()
    if env:
        return Path(env).expanduser()

    # Common defaults
    candidates: list[Path] = []
    xdg_data_home = (os.environ.get("XDG_DATA_HOME") or "").strip()
    if xdg_data_home:
        candidates.append(Path(xdg_data_home) / "opencode" / "storage")
    candidates.append(Path.home() / ".local" / "share" / "opencode" / "storage")

    # Windows native (best-effort; OpenCode might not use this, but allow it if present)
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        candidates.append(Path(localappdata) / "opencode" / "storage")
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "opencode" / "storage")
    # Windows fallback when env vars are missing.
    candidates.append(Path.home() / "AppData" / "Local" / "opencode" / "storage")
    candidates.append(Path.home() / "AppData" / "Roaming" / "opencode" / "storage")

    # WSL: OpenCode may run on Windows and store data under C:\Users\<name>\AppData\...\opencode\storage.
    # Try common /mnt/c mappings.
    if _is_wsl():
        users_root = Path("/mnt/c/Users")
        if users_root.exists():
            preferred_names: list[str] = []
            for k in ("WINUSER", "USERNAME", "USER"):
                v = (os.environ.get(k) or "").strip()
                if v and v not in preferred_names:
                    preferred_names.append(v)
            for name in preferred_names:
                candidates.append(users_root / name / "AppData" / "Local" / "opencode" / "storage")
                candidates.append(users_root / name / "AppData" / "Roaming" / "opencode" / "storage")

            # If still not found, scan for any matching storage dir and pick the most recently modified.
            found: list[Path] = []
            try:
                for user_dir in users_root.iterdir():
                    if not user_dir.is_dir():
                        continue
                    for p in (
                        user_dir / "AppData" / "Local" / "opencode" / "storage",
                        user_dir / "AppData" / "Roaming" / "opencode" / "storage",
                    ):
                        if p.exists():
                            found.append(p)
            except Exception:
                found = []
            if found:
                found.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
                candidates.insert(0, found[0])

    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except Exception:
            continue

    # Fallback to Linux default even if it doesn't exist yet (ping/health will report).
    return candidates[0]


OPENCODE_STORAGE_ROOT = _default_opencode_storage_root()

def _default_opencode_log_root() -> Path:
    env = (os.environ.get("OPENCODE_LOG_ROOT") or "").strip()
    if env:
        return Path(env).expanduser()

    candidates: list[Path] = []
    xdg_data_home = (os.environ.get("XDG_DATA_HOME") or "").strip()
    if xdg_data_home:
        candidates.append(Path(xdg_data_home) / "opencode" / "log")
    candidates.append(Path.home() / ".local" / "share" / "opencode" / "log")
    candidates.append(Path.home() / ".opencode" / "log")

    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except Exception:
            continue

    return candidates[0]


OPENCODE_LOG_ROOT = _default_opencode_log_root()


def _latest_opencode_log_file(root: Path = OPENCODE_LOG_ROOT) -> Path | None:
    try:
        if not root.exists():
            return None
        paths = [p for p in root.glob("*.log") if p.is_file()]
    except Exception:
        return None
    if not paths:
        return None
    try:
        paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        paths.sort()
    return paths[0]


def _is_cancel_log_line(line: str, *, session_id: str) -> bool:
    if not line:
        return False
    sid = (session_id or "").strip()
    if not sid:
        return False
    if f"sessionID={sid} cancel" in line:
        return True
    if f"path=/session/{sid}/abort" in line:
        return True
    return False


def _parse_opencode_log_epoch_s(line: str) -> float | None:
    """
    Parse OpenCode log timestamp into epoch seconds (UTC).

    Observed format: "INFO  2026-01-09T12:11:12 +1ms service=..."
    """
    try:
        parts = (line or "").split()
        if len(parts) < 2:
            return None
        ts = parts[1]
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        return float(dt.timestamp())
    except Exception:
        return None


class OpenCodeLogReader:
    """
    Reads OpenCode session/message/part JSON files.

    Observed storage layout:
      storage/session/<projectID>/ses_*.json
      storage/message/<sessionID>/msg_*.json
      storage/part/<messageID>/prt_*.json
    """

    def __init__(
        self,
        root: Path = OPENCODE_STORAGE_ROOT,
        work_dir: Optional[Path] = None,
        project_id: str = "global",
        *,
        session_id_filter: str | None = None,
    ):
        self.root = Path(root).expanduser()
        self.work_dir = work_dir or Path.cwd()
        env_project_id = (os.environ.get("OPENCODE_PROJECT_ID") or "").strip()
        explicit_project_id = bool(env_project_id) or ((project_id or "").strip() not in ("", "global"))
        self._allow_parent_match = _env_truthy("OPENCODE_ALLOW_PARENT_WORKDIR_MATCH")
        self._allow_any_session = _env_truthy("OPENCODE_ALLOW_ANY_SESSION")
        allow_git_root_fallback = _env_truthy("OPENCODE_ALLOW_GIT_ROOT_FALLBACK")
        self.project_id = (env_project_id or project_id or "global").strip() or "global"
        self._session_id_filter = (session_id_filter or "").strip() or None
        if not explicit_project_id:
            detected = self._detect_project_id_for_workdir()
            if detected:
                self.project_id = detected
            elif allow_git_root_fallback:
                # Fallback for older storage layouts or path-matching issues.
                self.project_id = compute_opencode_project_id(self.work_dir)

        try:
            poll = float(os.environ.get("OPENCODE_POLL_INTERVAL", "0.05"))
        except Exception:
            poll = 0.05
        self._poll_interval = min(0.5, max(0.02, poll))

        try:
            force = float(os.environ.get("OPENCODE_FORCE_READ_INTERVAL", "1.0"))
        except Exception:
            force = 1.0
        self._force_read_interval = min(5.0, max(0.2, force))

    def _session_dir(self) -> Path:
        return self.root / "session" / self.project_id

    def _message_dir(self, session_id: str) -> Path:
        # Preferred nested layout: message/<sessionID>/*.json
        nested = self.root / "message" / session_id
        if nested.exists():
            return nested
        # Fallback legacy layout: message/*.json
        return self.root / "message"

    def _part_dir(self, message_id: str) -> Path:
        nested = self.root / "part" / message_id
        if nested.exists():
            return nested
        return self.root / "part"

    def _work_dir_candidates(self) -> list[str]:
        candidates: list[str] = []
        env_pwd = (os.environ.get("PWD") or "").strip()
        if env_pwd:
            candidates.append(env_pwd)
        candidates.append(str(self.work_dir))
        try:
            candidates.append(str(self.work_dir.resolve()))
        except Exception:
            pass
        # Normalize and de-dup
        seen: set[str] = set()
        out: list[str] = []
        for c in candidates:
            norm = _normalize_path_for_match(c)
            if norm and norm not in seen:
                seen.add(norm)
                out.append(norm)
        return out

    def _load_json(self, path: Path) -> dict:
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _detect_project_id_for_workdir(self) -> Optional[str]:
        """
        Auto-detect OpenCode projectID based on storage/project/*.json.

        Without this, using the default "global" project can accidentally bind to an unrelated
        session whose directory is a parent of the current cwd, causing reply polling to miss.
        """
        projects_dir = self.root / "project"
        if not projects_dir.exists():
            return None

        work_candidates = self._work_dir_candidates()
        best_id: str | None = None
        best_score: tuple[int, int, float] = (-1, -1, -1.0)

        try:
            paths = [p for p in projects_dir.glob("*.json") if p.is_file()]
        except Exception:
            paths = []

        for path in paths:
            payload = self._load_json(path)

            pid = payload.get("id") if isinstance(payload.get("id"), str) and payload.get("id") else path.stem
            worktree = payload.get("worktree")
            if not isinstance(pid, str) or not pid:
                continue
            if not isinstance(worktree, str) or not worktree:
                continue

            worktree_norm = _normalize_path_for_match(worktree)
            if not worktree_norm:
                continue

            # Require the project worktree to contain our cwd (avoid picking an arbitrary child project
            # when running from a higher-level directory).
            if not any(_path_matches(worktree_norm, c, allow_parent=self._allow_parent_match) for c in work_candidates):
                continue

            updated = (payload.get("time") or {}).get("updated")
            try:
                updated_i = int(updated)
            except Exception:
                updated_i = -1
            try:
                mtime = path.stat().st_mtime
            except Exception:
                mtime = 0.0

            score = (len(worktree_norm), updated_i, mtime)
            if score > best_score:
                best_id = pid
                best_score = score

        return best_id

    def _get_latest_session(self) -> Optional[dict]:
        sessions_dir = self._session_dir()
        if not sessions_dir.exists():
            return None

        # Look up the filtered session (if any) but don't return immediately;
        # we need to check if there's a newer session for the same work_dir.
        filtered_match: dict | None = None
        filtered_updated: int = -1
        if self._session_id_filter:
            try:
                for path in sessions_dir.glob("ses_*.json"):
                    if not path.is_file():
                        continue
                    payload = self._load_json(path)
                    sid = payload.get("id")
                    if isinstance(sid, str) and sid == self._session_id_filter:
                        filtered_match = {"path": path, "payload": payload}
                        try:
                            filtered_updated = int((payload.get("time") or {}).get("updated") or -1)
                        except Exception:
                            filtered_updated = -1
                        break
            except Exception:
                pass

        candidates = self._work_dir_candidates()
        best_match: dict | None = None
        best_updated = -1
        best_mtime = -1.0
        best_any: dict | None = None
        best_any_updated = -1
        best_any_mtime = -1.0

        try:
            files = [p for p in sessions_dir.glob("ses_*.json") if p.is_file()]
        except Exception:
            files = []

        for path in files:
            payload = self._load_json(path)
            sid = payload.get("id")
            directory = payload.get("directory")
            updated = (payload.get("time") or {}).get("updated")
            if not isinstance(sid, str) or not sid:
                continue
            if not isinstance(updated, int):
                try:
                    updated = int(updated)
                except Exception:
                    updated = -1
            try:
                mtime = path.stat().st_mtime
            except Exception:
                mtime = 0.0

            # Track best-any for fallback
            if updated > best_any_updated or (updated == best_any_updated and mtime >= best_any_mtime):
                best_any = {"path": path, "payload": payload}
                best_any_updated = updated
                best_any_mtime = mtime

            if not isinstance(directory, str) or not directory:
                continue
            session_dir_norm = _normalize_path_for_match(directory)
            matched = False
            for cwd in candidates:
                if self._allow_parent_match:
                    if _path_is_same_or_parent(session_dir_norm, cwd) or _path_is_same_or_parent(cwd, session_dir_norm):
                        matched = True
                        break
                else:
                    if session_dir_norm == cwd:
                        matched = True
                        break
            if not matched:
                continue

            if updated > best_updated or (updated == best_updated and mtime >= best_mtime):
                best_match = {"path": path, "payload": payload}
                best_updated = updated
                best_mtime = mtime

        # If we have a filtered match, use it only if there's no newer work_dir match.
        # This handles the case where OpenCode was restarted and created a new session.
        if filtered_match:
            if best_match and best_updated > filtered_updated:
                # A newer session exists for the same work_dir; prefer it over stale binding.
                return best_match
            return filtered_match

        if best_match:
            return best_match
        if self._allow_any_session:
            return best_any
        return None

    def _read_messages(self, session_id: str) -> List[dict]:
        message_dir = self._message_dir(session_id)
        if not message_dir.exists():
            return []
        messages: list[dict] = []
        try:
            paths = [p for p in message_dir.glob("msg_*.json") if p.is_file()]
        except Exception:
            paths = []
        for path in paths:
            payload = self._load_json(path)
            if payload.get("sessionID") != session_id:
                continue
            payload["_path"] = str(path)
            messages.append(payload)
        # Sort by created time (ms), fallback to mtime
        def _key(m: dict) -> tuple[int, float, str]:
            created = (m.get("time") or {}).get("created")
            try:
                created_i = int(created)
            except Exception:
                created_i = -1
            try:
                mtime = Path(m.get("_path", "")).stat().st_mtime if m.get("_path") else 0.0
            except Exception:
                mtime = 0.0
            mid = m.get("id") if isinstance(m.get("id"), str) else ""
            return created_i, mtime, mid

        messages.sort(key=_key)
        return messages

    def _read_parts(self, message_id: str) -> List[dict]:
        part_dir = self._part_dir(message_id)
        if not part_dir.exists():
            return []
        parts: list[dict] = []
        try:
            paths = [p for p in part_dir.glob("prt_*.json") if p.is_file()]
        except Exception:
            paths = []
        for path in paths:
            payload = self._load_json(path)
            if payload.get("messageID") != message_id:
                continue
            payload["_path"] = str(path)
            parts.append(payload)

        def _key(p: dict) -> tuple[int, float, str]:
            ts = (p.get("time") or {}).get("start")
            try:
                ts_i = int(ts)
            except Exception:
                ts_i = -1
            try:
                mtime = Path(p.get("_path", "")).stat().st_mtime if p.get("_path") else 0.0
            except Exception:
                mtime = 0.0
            pid = p.get("id") if isinstance(p.get("id"), str) else ""
            return ts_i, mtime, pid

        parts.sort(key=_key)
        return parts

    @staticmethod
    def _extract_text(parts: List[dict], allow_reasoning_fallback: bool = True) -> str:
        def _collect(types: set[str]) -> str:
            out: list[str] = []
            for part in parts:
                if part.get("type") not in types:
                    continue
                text = part.get("text")
                if isinstance(text, str) and text:
                    out.append(text)
            return "".join(out).strip()

        # Prefer final visible content when present.
        text = _collect({"text"})
        if text:
            return text

        # Fallback: some OpenCode runs only emit reasoning parts without a separate "text" part.
        if allow_reasoning_fallback:
            return _collect({"reasoning"})
        return ""

    def capture_state(self) -> Dict[str, Any]:
        session_entry = self._get_latest_session()
        if not session_entry:
            return {"session_id": None, "session_updated": -1, "assistant_count": 0, "last_assistant_id": None}

        payload = session_entry.get("payload") or {}
        session_id = payload.get("id") if isinstance(payload.get("id"), str) else None
        updated = (payload.get("time") or {}).get("updated")
        try:
            updated_i = int(updated)
        except Exception:
            updated_i = -1

        assistant_count = 0
        last_assistant_id: str | None = None
        last_completed: int | None = None

        if session_id:
            messages = self._read_messages(session_id)
            for msg in messages:
                if msg.get("role") == "assistant":
                    assistant_count += 1
                    mid = msg.get("id")
                    if isinstance(mid, str):
                        last_assistant_id = mid
                        completed = (msg.get("time") or {}).get("completed")
                        try:
                            last_completed = int(completed) if completed is not None else None
                        except Exception:
                            last_completed = None

        return {
            "session_path": session_entry.get("path"),
            "session_id": session_id,
            "session_updated": updated_i,
            "assistant_count": assistant_count,
            "last_assistant_id": last_assistant_id,
            "last_assistant_completed": last_completed,
        }

    def _find_new_assistant_reply(self, session_id: str, state: Dict[str, Any]) -> Optional[str]:
        prev_count = int(state.get("assistant_count") or 0)
        prev_last = state.get("last_assistant_id")
        prev_completed = state.get("last_assistant_completed")

        messages = self._read_messages(session_id)
        assistants = [m for m in messages if m.get("role") == "assistant" and isinstance(m.get("id"), str)]
        if not assistants:
            return None

        latest = assistants[-1]
        latest_id = latest.get("id")
        completed = (latest.get("time") or {}).get("completed")
        try:
            completed_i = int(completed) if completed is not None else None
        except Exception:
            completed_i = None

        # If assistant is still streaming, wait (prefer completed reply).
        if completed_i is None:
            # Fallback: some OpenCode builds may omit completed timestamps.
            # If the message already contains a completion marker, treat it as complete.
            parts = self._read_parts(str(latest_id))
            text = self._extract_text(parts, allow_reasoning_fallback=False)
            completion_marker = (os.environ.get("CCB_EXECUTION_COMPLETE_MARKER") or "[EXECUTION_COMPLETE]").strip() or "[EXECUTION_COMPLETE]"
            has_done = bool(text) and ("CCB_DONE:" in text)
            if text and (completion_marker in text or has_done):
                completed_i = int(time.time() * 1000)
            else:
                return None  # Still streaming, wait

        # Detect change via count or last id or completion timestamp.
        # If nothing changed, no new reply yet - keep waiting.
        if len(assistants) <= prev_count and latest_id == prev_last and completed_i == prev_completed:
            return None

        parts = self._read_parts(str(latest_id))
        # Prefer text content; if empty and completed, fallback to reasoning
        text = self._extract_text(parts, allow_reasoning_fallback=False)
        if not text and completed_i is not None:
            text = self._extract_text(parts, allow_reasoning_fallback=True)
        return text or None

    def _read_since(self, state: Dict[str, Any], timeout: float, block: bool) -> Tuple[Optional[str], Dict[str, Any]]:
        deadline = time.time() + timeout
        last_forced_read = time.time()

        session_id = state.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            session_id = None

        while True:
            session_entry = self._get_latest_session()
            if not session_entry:
                if not block:
                    return None, state
                time.sleep(self._poll_interval)
                if time.time() >= deadline:
                    return None, state
                continue

            payload = session_entry.get("payload") or {}
            current_session_id = payload.get("id") if isinstance(payload.get("id"), str) else None
            if session_id and current_session_id and current_session_id != session_id:
                # Check if new session has a completed reply - if so, follow it
                new_reply = self._find_new_assistant_reply(current_session_id, {"assistant_count": 0})
                if new_reply:
                    # New session has reply, switch to it
                    session_id = current_session_id
                else:
                    # No reply in new session yet, keep old session
                    current_session_id = session_id
            elif not session_id:
                session_id = current_session_id

            if not current_session_id:
                if not block:
                    return None, state
                time.sleep(self._poll_interval)
                if time.time() >= deadline:
                    return None, state
                continue

            updated = (payload.get("time") or {}).get("updated")
            try:
                updated_i = int(updated)
            except Exception:
                updated_i = -1

            prev_updated = int(state.get("session_updated") or -1)
            should_scan = updated_i != prev_updated
            if block and not should_scan and (time.time() - last_forced_read) >= self._force_read_interval:
                should_scan = True
                last_forced_read = time.time()

            if should_scan:
                reply = self._find_new_assistant_reply(current_session_id, state)
                if reply:
                    new_state = self.capture_state()
                    # Preserve session binding
                    if session_id:
                        new_state["session_id"] = session_id
                    return reply, new_state

                # Update state baseline even if reply isn't ready yet.
                state = dict(state)
                state["session_updated"] = updated_i

            if not block:
                return None, state

            time.sleep(self._poll_interval)
            if time.time() >= deadline:
                return None, state

    def wait_for_message(self, state: Dict[str, Any], timeout: float) -> Tuple[Optional[str], Dict[str, Any]]:
        return self._read_since(state, timeout, block=True)

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        return self._read_since(state, timeout=0.0, block=False)

    def latest_message(self) -> Optional[str]:
        session_entry = self._get_latest_session()
        if not session_entry:
            return None
        payload = session_entry.get("payload") or {}
        session_id = payload.get("id")
        if not isinstance(session_id, str) or not session_id:
            return None
        messages = self._read_messages(session_id)
        assistants = [m for m in messages if m.get("role") == "assistant" and isinstance(m.get("id"), str)]
        if not assistants:
            return None
        latest = assistants[-1]
        completed = (latest.get("time") or {}).get("completed")
        if completed is None:
            return None
        parts = self._read_parts(str(latest.get("id")))
        text = self._extract_text(parts)
        return text or None

    @staticmethod
    def _is_aborted_error(error_obj: object) -> bool:
        if not isinstance(error_obj, dict):
            return False
        name = error_obj.get("name")
        if isinstance(name, str) and "aborted" in name.lower():
            return True
        data = error_obj.get("data")
        if isinstance(data, dict):
            msg = data.get("message")
            if isinstance(msg, str) and ("aborted" in msg.lower() or "cancel" in msg.lower()):
                return True
        return False

    @staticmethod
    def _extract_req_id_from_text(text: str) -> Optional[str]:
        if not text:
            return None
        m = _REQ_ID_RE.search(text)
        return m.group(1).lower() if m else None

    def detect_cancelled_since(self, state: Dict[str, Any], *, req_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Detect whether the request with `req_id` was cancelled/aborted.

        Observed OpenCode cancellation behavior:
        - A new assistant message is written with an `error` like:
          {"name":"MessageAbortedError","data":{"message":"The operation was aborted."}}
        - That assistant message contains no text parts, so naive reply polling misses it.
        """
        req_id = (req_id or "").strip().lower()
        if not req_id:
            return False, state

        try:
            prev_count = int(state.get("assistant_count") or 0)
        except Exception:
            prev_count = 0
        prev_last = state.get("last_assistant_id")
        prev_completed = state.get("last_assistant_completed")

        new_state = self.capture_state()
        session_id = new_state.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            return False, new_state

        messages = self._read_messages(session_id)
        assistants = [m for m in messages if m.get("role") == "assistant" and isinstance(m.get("id"), str)]
        by_id: dict[str, dict] = {str(m.get("id")): m for m in assistants if isinstance(m.get("id"), str)}

        candidates: list[dict] = []
        if prev_count < len(assistants):
            candidates.extend(assistants[prev_count:])

        # Cancellation can be recorded by updating an existing in-flight assistant message in-place
        # (assistant_count unchanged). Always inspect the latest assistant message, and also inspect the
        # previous last assistant message when its completed timestamp changed.
        last_id = new_state.get("last_assistant_id")
        if isinstance(last_id, str) and last_id in by_id and by_id[last_id] not in candidates:
            candidates.append(by_id[last_id])
        if (
            isinstance(prev_last, str)
            and prev_last in by_id
            and prev_last != last_id
            and by_id[prev_last] not in candidates
        ):
            # Include the previous last assistant too (rare session switching / reordering).
            candidates.append(by_id[prev_last])
        if (
            isinstance(prev_last, str)
            and prev_last in by_id
            and prev_last == last_id
            and by_id[prev_last] not in candidates
            and new_state.get("last_assistant_completed") != prev_completed
        ):
            candidates.append(by_id[prev_last])

        if not candidates:
            return False, new_state

        for msg in candidates:
            if not self._is_aborted_error(msg.get("error")):
                continue
            parent_id = msg.get("parentID")
            if not isinstance(parent_id, str) or not parent_id:
                continue
            parts = self._read_parts(parent_id)
            prompt_text = self._extract_text(parts, allow_reasoning_fallback=True)
            prompt_req_id = self._extract_req_id_from_text(prompt_text)
            if prompt_req_id and prompt_req_id == req_id:
                return True, new_state

        return False, new_state

    def open_cancel_log_cursor(self) -> Dict[str, Any]:
        """
        Create a cursor that tails OpenCode's server logs for cancellation/abort events.

        The cursor starts at EOF so only future lines are considered.
        """
        path = _latest_opencode_log_file()
        if not path:
            return {"path": None, "offset": 0}
        try:
            offset = int(path.stat().st_size)
        except Exception:
            offset = 0
        return {"path": str(path), "offset": offset, "mtime": float(path.stat().st_mtime) if path.exists() else 0.0}

    def detect_cancel_event_in_logs(
        self, cursor: Dict[str, Any], *, session_id: str, since_epoch_s: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Detect cancellation based on OpenCode log lines.

        This is a fallback for the race where the user interrupts before the prompt/aborted message
        is persisted into storage.
        """
        if not isinstance(cursor, dict):
            cursor = {}
        current_path = cursor.get("path")
        offset = cursor.get("offset")
        cursor_mtime = cursor.get("mtime")
        try:
            offset_i = int(offset) if offset is not None else 0
        except Exception:
            offset_i = 0
        try:
            cursor_mtime_f = float(cursor_mtime) if cursor_mtime is not None else 0.0
        except Exception:
            cursor_mtime_f = 0.0

        latest = _latest_opencode_log_file()
        if latest is None:
            return False, {"path": None, "offset": 0, "mtime": 0.0}

        path = Path(str(current_path)) if isinstance(current_path, str) and current_path else None
        if path is None or not path.exists():
            path = latest
            offset_i = 0
            cursor_mtime_f = 0.0
        elif latest != path:
            # Prefer staying on the same file unless the latest file is clearly newer than our cursor.
            try:
                latest_mtime = float(latest.stat().st_mtime)
            except Exception:
                latest_mtime = 0.0
            if latest_mtime > cursor_mtime_f + 0.5:
                path = latest
                offset_i = 0
                cursor_mtime_f = 0.0

        try:
            size = int(path.stat().st_size)
        except Exception:
            return False, {"path": str(path), "offset": 0, "mtime": cursor_mtime_f}

        if offset_i < 0 or offset_i > size:
            offset_i = 0

        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(offset_i)
                chunk = handle.read()
        except Exception:
            return False, {"path": str(path), "offset": size, "mtime": cursor_mtime_f}

        try:
            new_cursor_mtime = float(path.stat().st_mtime)
        except Exception:
            new_cursor_mtime = cursor_mtime_f
        new_cursor = {"path": str(path), "offset": size, "mtime": new_cursor_mtime}
        if not chunk:
            return False, new_cursor

        for line in chunk.splitlines():
            if not _is_cancel_log_line(line, session_id=session_id):
                continue
            ts = _parse_opencode_log_epoch_s(line)
            if ts is None:
                continue
            if ts + 0.1 < float(since_epoch_s):
                continue
            return True, new_cursor

        return False, new_cursor


class OpenCodeCommunicator:
    def __init__(self, lazy_init: bool = False):
        self.session_info = self._load_session_info()
        if not self.session_info:
            raise RuntimeError("❌ No active OpenCode session found. Run 'ccb opencode' (or add opencode to ccb.config) first")

        self.session_id = self.session_info["session_id"]
        self.runtime_dir = Path(self.session_info["runtime_dir"])
        self.terminal = self.session_info.get("terminal", os.environ.get("OPENCODE_TERMINAL", "tmux"))
        self.pane_id = get_pane_id_from_session(self.session_info) or ""
        self.backend = get_backend_for_session(self.session_info)

        self.timeout = int(os.environ.get("OPENCODE_SYNC_TIMEOUT", "30"))
        self.marker_prefix = "oask"
        self.project_session_file = self.session_info.get("_session_file")

        # Prefer storage-based autodetection instead of git-derived project ids when possible.
        self.log_reader = OpenCodeLogReader(
            work_dir=Path(self.session_info.get("work_dir") or Path.cwd()),
            project_id="global",
            session_id_filter=(str(self.session_info.get("opencode_session_id") or "").strip() or None),
        )

        # Best-effort: publish to registry for project_id routing.
        try:
            wd = self.session_info.get("work_dir")
            ccb_pid = compute_ccb_project_id(Path(wd)) if isinstance(wd, str) and wd else ""
            upsert_registry(
                {
                    "ccb_session_id": self.session_id,
                    "ccb_project_id": ccb_pid or None,
                    "work_dir": wd,
                    "terminal": self.terminal,
                    "providers": {
                        "opencode": {
                            "pane_id": self.pane_id or None,
                            "pane_title_marker": self.session_info.get("pane_title_marker"),
                            "session_file": self.project_session_file,
                            "opencode_project_id": self.session_info.get("opencode_project_id"),
                            "opencode_session_id": self.session_info.get("opencode_session_id"),
                        }
                    },
                }
            )
        except Exception:
            pass

        if not lazy_init:
            healthy, msg = self._check_session_health()
            if not healthy:
                raise RuntimeError(f"❌ Session unhealthy: {msg}\nTip: Run 'ccb opencode' (or add opencode to ccb.config) to start a new session")

    def _find_session_file(self) -> Optional[Path]:
        env_session = (os.environ.get("CCB_SESSION_FILE") or "").strip()
        if env_session:
            try:
                session_path = Path(os.path.expanduser(env_session))
                if session_path.name == ".opencode-session" and session_path.is_file():
                    return session_path
            except Exception:
                pass
        return find_project_session_file(Path.cwd(), ".opencode-session")

    def _load_session_info(self) -> Optional[dict]:
        if "OPENCODE_SESSION_ID" in os.environ:
            terminal = os.environ.get("OPENCODE_TERMINAL", "tmux")
            if terminal == "wezterm":
                pane_id = os.environ.get("OPENCODE_WEZTERM_PANE", "")
            else:
                pane_id = ""
            result = {
                "session_id": os.environ["OPENCODE_SESSION_ID"],
                "runtime_dir": os.environ["OPENCODE_RUNTIME_DIR"],
                "terminal": terminal,
                "tmux_session": os.environ.get("OPENCODE_TMUX_SESSION", ""),
                "pane_id": pane_id,
                "_session_file": None,
            }
            session_file = self._find_session_file()
            if session_file:
                try:
                    with session_file.open("r", encoding="utf-8-sig") as handle:
                        file_data = json.load(handle)
                    if isinstance(file_data, dict):
                        result["opencode_session_path"] = file_data.get("opencode_session_path")
                        result["_session_file"] = str(session_file)
                except Exception:
                    pass
            return result

        project_session = self._find_session_file()
        if not project_session:
            return None

        try:
            with project_session.open("r", encoding="utf-8-sig") as handle:
                data = json.load(handle)

            if not isinstance(data, dict) or not data.get("active", False):
                return None

            runtime_dir = Path(data.get("runtime_dir", ""))
            if not runtime_dir.exists():
                return None

            data["_session_file"] = str(project_session)

            # Best-effort migration: ensure ccb_project_id is present.
            try:
                if not (data.get("ccb_project_id") or "").strip():
                    wd = data.get("work_dir")
                    if isinstance(wd, str) and wd.strip():
                        data["ccb_project_id"] = compute_ccb_project_id(Path(wd.strip()))
                        safe_write_session(project_session, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            except Exception:
                pass
            return data
        except Exception:
            return None

    def _check_session_health(self) -> Tuple[bool, str]:
        return self._check_session_health_impl(probe_terminal=True)

    def _check_session_health_impl(self, probe_terminal: bool) -> Tuple[bool, str]:
        try:
            if not self.runtime_dir.exists():
                return False, "Runtime directory not found"
            if not self.pane_id:
                return False, "Session pane not found"
            if probe_terminal and self.backend and not self.backend.is_alive(self.pane_id):
                return False, f"{self.terminal} session {self.pane_id} not found"

            # Storage health check (reply reader)
            if not OPENCODE_STORAGE_ROOT.exists():
                return False, f"OpenCode storage not found: {OPENCODE_STORAGE_ROOT}"
            return True, "Session OK"
        except Exception as exc:
            return False, f"Check failed: {exc}"

    def ping(self, display: bool = True) -> Tuple[bool, str]:
        healthy, status = self._check_session_health()
        msg = f"✅ OpenCode connection OK ({status})" if healthy else f"❌ OpenCode connection error: {status}"
        if display:
            print(msg)
        return healthy, msg

    def _send_via_terminal(self, content: str) -> None:
        if not self.backend or not self.pane_id:
            raise RuntimeError("Terminal session not configured")
        self.backend.send_text(self.pane_id, content)

    def _send_message(self, content: str) -> Tuple[str, Dict[str, Any]]:
        marker = self._generate_marker()
        state = self.log_reader.capture_state()
        self._send_via_terminal(content)
        return marker, state

    def _generate_marker(self) -> str:
        return f"{self.marker_prefix}-{int(time.time())}-{os.getpid()}"

    def ask_async(self, question: str) -> bool:
        try:
            healthy, status = self._check_session_health_impl(probe_terminal=False)
            if not healthy:
                raise RuntimeError(f"❌ Session error: {status}")
            self._send_via_terminal(question)
            print("✅ Sent to OpenCode")
            print("Hint: Use opend to view reply")
            return True
        except Exception as exc:
            print(f"❌ Send failed: {exc}")
            return False

    def ask_sync(self, question: str, timeout: Optional[int] = None) -> Optional[str]:
        try:
            healthy, status = self._check_session_health_impl(probe_terminal=False)
            if not healthy:
                raise RuntimeError(f"❌ Session error: {status}")

            print(f"🔔 {t('sending_to', provider='OpenCode')}", flush=True)
            _, state = self._send_message(question)
            wait_timeout = self.timeout if timeout is None else int(timeout)
            print(f"⏳ Waiting for OpenCode reply (timeout {wait_timeout}s)...")
            message, _ = self.log_reader.wait_for_message(state, float(wait_timeout))
            if message:
                print(f"🤖 {t('reply_from', provider='OpenCode')}")
                print(message)
                return message
            print(f"⏰ {t('timeout_no_reply', provider='OpenCode')}")
            return None
        except Exception as exc:
            print(f"❌ Sync ask failed: {exc}")
            return None
