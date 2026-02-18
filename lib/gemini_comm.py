"""
Gemini communication module
Supports tmux and WezTerm terminals, reads replies from ~/.gemini/tmp/<hash>/chats/session-*.json
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import threading
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from terminal import get_backend_for_session, get_pane_id_from_session
from ccb_config import apply_backend_env
from i18n import t
from session_utils import find_project_session_file
from session_file_watcher import SessionFileWatcher, HAS_WATCHDOG
from pane_registry import upsert_registry
from project_id import compute_ccb_project_id

apply_backend_env()

GEMINI_ROOT = Path(os.environ.get("GEMINI_ROOT") or (Path.home() / ".gemini" / "tmp")).expanduser()

_GEMINI_WATCHER: Optional[SessionFileWatcher] = None
_GEMINI_WATCH_STARTED = False
_GEMINI_WATCH_LOCK = threading.Lock()
_GEMINI_HASH_CACHE: dict[str, list[Path]] = {}
_GEMINI_HASH_CACHE_TS = 0.0



def _is_ccb_instance_dir(work_dir: Path) -> bool:
    """Detect ccb-multi instance directories.

    These have generic basenames that collide across projects, so SHA-256
    should be preferred over basename for Gemini session lookup.

    Detection (any match = True):
      1) CCB_INSTANCE_ID env var is set (ccb-multi always sets this)
      2) Parent directory is named '.ccb-instances'
    """
    if os.environ.get("CCB_INSTANCE_ID", "").strip():
        return True
    try:
        abs_path = work_dir.expanduser().absolute()
    except Exception:
        abs_path = work_dir
    return abs_path.parent.name == ".ccb-instances"


def _compute_project_hashes(work_dir: Optional[Path] = None) -> tuple[str, str]:
    """Return ``(basename_hash, sha256_hash)`` for *work_dir*.

    Gemini CLI >= 0.29.0 uses the directory basename; older versions used
    SHA-256 of the absolute path.  Callers that need to probe both formats
    should use this helper.
    """
    path = work_dir or Path.cwd()
    try:
        abs_path = path.expanduser().absolute()
    except Exception:
        abs_path = path
    basename_hash = abs_path.name
    sha256_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()
    return basename_hash, sha256_hash


def _get_project_hash(work_dir: Optional[Path] = None) -> str:
    """Return the *primary* project hash for *work_dir*.

    Prefers the new basename format when its ``chats/`` directory exists,
    falls back to SHA-256, and defaults to basename for forward compat.

    For ccb-multi instance directories (e.g. instance-1), prefer SHA-256
    to avoid cross-project basename collisions.
    """
    path = work_dir or Path.cwd()
    basename_hash, sha256_hash = _compute_project_hashes(path)
    root = Path(os.environ.get("GEMINI_ROOT") or (Path.home() / ".gemini" / "tmp")).expanduser()
    is_instance = _is_ccb_instance_dir(path)

    if is_instance:
        # Old instance dirs (instance-1, ...) have generic basenames that
        # collide across projects. New format (inst-<hash>-N) is unique, but
        # we still prefer SHA-256 for backward compat with old instances.
        if (root / sha256_hash / "chats").is_dir():
            return sha256_hash
        if (root / basename_hash / "chats").is_dir():
            return basename_hash
        return sha256_hash
    else:
        if (root / basename_hash / "chats").is_dir():
            return basename_hash
        if (root / sha256_hash / "chats").is_dir():
            return sha256_hash
        return basename_hash


def _iter_registry_work_dirs() -> list[Path]:
    registry_dir = Path.home() / ".ccb" / "run"
    if not registry_dir.exists():
        return []
    work_dirs: list[Path] = []
    try:
        paths = list(registry_dir.glob("ccb-session-*.json"))
    except Exception:
        paths = []
    for path in paths:
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        wd = data.get("work_dir")
        if isinstance(wd, str) and wd.strip():
            try:
                work_dirs.append(Path(wd.strip()).expanduser())
            except Exception:
                continue
    return work_dirs


def _work_dirs_for_hash(project_hash: str) -> list[Path]:
    global _GEMINI_HASH_CACHE_TS, _GEMINI_HASH_CACHE
    now = time.time()
    if now - _GEMINI_HASH_CACHE_TS > 5.0:
        _GEMINI_HASH_CACHE = {}
        for wd in _iter_registry_work_dirs():
            try:
                # Register both hash formats so the watchdog can match either
                bn, sha = _compute_project_hashes(wd)
                for h in (bn, sha):
                    _GEMINI_HASH_CACHE.setdefault(h, []).append(wd)
            except Exception:
                continue
        _GEMINI_HASH_CACHE_TS = now
    return _GEMINI_HASH_CACHE.get(project_hash, [])


def _read_gemini_session_id(session_path: Path) -> str:
    if not session_path or not session_path.exists():
        return ""
    for _ in range(5):
        try:
            payload = json.loads(session_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            time.sleep(0.05)
            continue
        except Exception:
            return ""
        if isinstance(payload, dict) and isinstance(payload.get("sessionId"), str):
            return payload["sessionId"]
        return ""
    return ""


def _gemini_watch_predicate(path: Path) -> bool:
    return path.suffix == ".json" and path.name.startswith("session-")


def _handle_gemini_session_event(path: Path) -> None:
    if not path or not path.exists():
        return
    try:
        project_hash = path.parent.parent.name
    except Exception:
        project_hash = ""
    if not project_hash:
        return
    work_dirs = _work_dirs_for_hash(project_hash)
    if not work_dirs:
        return
    session_id = _read_gemini_session_id(path)
    for work_dir in work_dirs:
        session_file = find_project_session_file(work_dir, ".gemini-session")
        if not session_file or not session_file.exists():
            continue
        try:
            from gaskd_session import load_project_session
        except Exception:
            return
        session = load_project_session(work_dir)
        if not session:
            continue
        try:
            session.update_gemini_binding(session_path=path, session_id=session_id or None)
        except Exception:
            continue


def _ensure_gemini_watchdog_started() -> None:
    if not HAS_WATCHDOG:
        return
    global _GEMINI_WATCHER, _GEMINI_WATCH_STARTED
    if _GEMINI_WATCH_STARTED:
        return
    with _GEMINI_WATCH_LOCK:
        if _GEMINI_WATCH_STARTED:
            return
        if not GEMINI_ROOT.exists():
            return
        watcher = SessionFileWatcher(
            GEMINI_ROOT,
            _handle_gemini_session_event,
            recursive=True,
            predicate=_gemini_watch_predicate,
        )
        try:
            watcher.start()
        except Exception:
            return
        _GEMINI_WATCHER = watcher
        _GEMINI_WATCH_STARTED = True


class GeminiLogReader:
    """Reads Gemini session files from ~/.gemini/tmp/<hash>/chats"""

    def __init__(self, root: Path = GEMINI_ROOT, work_dir: Optional[Path] = None):
        self.root = Path(root).expanduser()
        self.work_dir = work_dir or Path.cwd()
        forced_hash = os.environ.get("GEMINI_PROJECT_HASH", "").strip()
        if forced_hash:
            self._project_hash = forced_hash
            self._all_known_hashes: set[str] = {forced_hash}
        else:
            self._project_hash = _get_project_hash(self.work_dir)
            bn, sha = _compute_project_hashes(self.work_dir)
            # Store all known hashes so they survive hash adoption
            self._all_known_hashes = {bn, sha}
        self._is_instance = _is_ccb_instance_dir(self.work_dir)
        self._preferred_session: Optional[Path] = None
        try:
            poll = float(os.environ.get("GEMINI_POLL_INTERVAL", "0.05"))
        except Exception:
            poll = 0.05
        self._poll_interval = min(0.5, max(0.02, poll))
        # Some filesystems only update mtime at 1s granularity. When waiting for a reply,
        # force a read periodically to avoid missing in-place updates that keep size/mtime unchanged.
        try:
            force = float(os.environ.get("GEMINI_FORCE_READ_INTERVAL", "1.0"))
        except Exception:
            force = 1.0
        self._force_read_interval = min(5.0, max(0.2, force))

    @staticmethod
    def _debug_enabled() -> bool:
        return os.environ.get("CCB_DEBUG") in ("1", "true", "yes") or os.environ.get("GPEND_DEBUG") in ("1", "true", "yes")

    @classmethod
    def _debug(cls, message: str) -> None:
        if not cls._debug_enabled():
            return
        print(f"[DEBUG] {message}", file=sys.stderr)

    def _chats_dir(self) -> Optional[Path]:
        chats = self.root / self._project_hash / "chats"
        return chats if chats.exists() else None

    def _scan_latest_session_any_project(self) -> Optional[Path]:
        """Scan latest session across all projectHash (fallback for Windows/WSL path hash mismatch)"""
        if not self.root.exists():
            return None
        try:
            sessions = sorted(
                (p for p in self.root.glob("*/chats/session-*.json") if p.is_file() and not p.name.startswith(".")),
                key=lambda p: p.stat().st_mtime,
            )
        except OSError:
            return None
        return sessions[-1] if sessions else None

    def _scan_latest_session(self) -> Optional[Path]:
        """Scan for the latest session file across all known hash dirs."""
        best: Optional[Path] = None
        best_mtime: float = 0.0

        # De-duplicate: primary first, then remaining known hashes
        seen: set[str] = set()
        scan_order: list[str] = []
        for h in [self._project_hash] + sorted(self._all_known_hashes - {self._project_hash}):
            if h not in seen:
                seen.add(h)
                scan_order.append(h)

        for project_hash in scan_order:
            chats = self.root / project_hash / "chats"
            if not chats.is_dir():
                continue
            try:
                for p in chats.glob("session-*.json"):
                    if not p.is_file() or p.name.startswith("."):
                        continue
                    try:
                        mt = p.stat().st_mtime
                    except OSError:
                        continue
                    if mt > best_mtime:
                        best = p
                        best_mtime = mt
            except OSError:
                continue

        # If the winning session lives under a different hash, adopt it
        # and add it to known hashes so future scans still cover all formats
        if best is not None:
            try:
                winning_hash = best.parent.parent.name
                if winning_hash:
                    self._all_known_hashes.add(winning_hash)
                    if winning_hash != self._project_hash:
                        self._project_hash = winning_hash
            except Exception:
                pass

        return best

    def _latest_session(self) -> Optional[Path]:
        preferred = self._preferred_session
        # Always scan to find the latest session by mtime
        scanned = self._scan_latest_session()

        # Compare preferred vs scanned by mtime - use whichever is newer
        if preferred and preferred.exists():
            if scanned and scanned.exists():
                try:
                    # For ccb-multi instance dirs, only accept scanned session
                    # from the SAME hash directory to prevent cross-project
                    # contamination via shared basename (old "instance-N" format).
                    if self._is_instance:
                        pref_hash = preferred.parent.parent.name
                        scan_hash = scanned.parent.parent.name
                        if pref_hash != scan_hash:
                            self._debug(f"Instance mode: ignoring cross-hash scan {scanned}")
                            return preferred

                    pref_mtime = preferred.stat().st_mtime
                    scan_mtime = scanned.stat().st_mtime
                    if scan_mtime > pref_mtime:
                        self._debug(f"Scanned session newer: {scanned} ({scan_mtime}) > {preferred} ({pref_mtime})")
                        self._preferred_session = scanned
                        return scanned
                except OSError:
                    pass
            self._debug(f"Using preferred session: {preferred}")
            return preferred

        if scanned:
            self._preferred_session = scanned
            self._debug(f"Scan found: {scanned}")
            return scanned
        # Strict by default: only scan this project's hash. Opt-in to any-project scan if needed.
        if os.environ.get("GEMINI_ALLOW_ANY_PROJECT_SCAN") in ("1", "true", "yes"):
            any_latest = self._scan_latest_session_any_project()
            if any_latest:
                self._preferred_session = any_latest
                try:
                    project_hash = any_latest.parent.parent.name
                    if project_hash:
                        self._project_hash = project_hash
                except Exception:
                    pass
                self._debug(f"Fallback scan (any project) found: {any_latest}")
                return any_latest
        return None

    def set_preferred_session(self, session_path: Optional[Path]) -> None:
        if not session_path:
            return
        try:
            candidate = session_path if isinstance(session_path, Path) else Path(str(session_path)).expanduser()
        except Exception:
            return
        if candidate.exists():
            self._preferred_session = candidate

    def current_session_path(self) -> Optional[Path]:
        return self._latest_session()

    def _read_session_json(self, session: Path) -> Optional[dict]:
        """
        Read a Gemini session JSON file with retries.

        Gemini CLI may write the session file in-place, causing transient JSONDecodeError.
        """
        if not session or not session.exists():
            return None
        for attempt in range(10):
            try:
                with session.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                return loaded if isinstance(loaded, dict) else None
            except json.JSONDecodeError:
                # Transient partial write; retry briefly.
                if attempt < 9:
                    time.sleep(min(self._poll_interval, 0.05))
                continue
            except OSError:
                return None
        return None

    def capture_state(self) -> Dict[str, Any]:
        """Record current session file and message count"""
        session = self._latest_session()
        msg_count = 0
        mtime = 0.0
        mtime_ns = 0
        size = 0
        last_gemini_id: Optional[str] = None
        last_gemini_hash: Optional[str] = None
        if session and session.exists():
            data: Optional[dict] = None
            try:
                stat = session.stat()
                mtime = stat.st_mtime
                mtime_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))
                size = stat.st_size
            except OSError:
                stat = None

            data = self._read_session_json(session)

            if data is None:
                # Unknown baseline (parse failed). Let the wait loop establish a stable baseline first.
                msg_count = -1
            else:
                msg_count = len(data.get("messages", []))
                last = self._extract_last_gemini(data)
                if last:
                    last_gemini_id, content = last
                    last_gemini_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return {
            "session_path": session,
            "msg_count": msg_count,
            "mtime": mtime,
            "mtime_ns": mtime_ns,
            "size": size,
            "last_gemini_id": last_gemini_id,
            "last_gemini_hash": last_gemini_hash,
        }

    def wait_for_message(self, state: Dict[str, Any], timeout: float) -> Tuple[Optional[str], Dict[str, Any]]:
        """Block and wait for new Gemini reply"""
        return self._read_since(state, timeout, block=True)

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        """Non-blocking read reply"""
        return self._read_since(state, timeout=0.0, block=False)

    def latest_message(self) -> Optional[str]:
        """Get the latest Gemini reply directly"""
        session = self._latest_session()
        if not session or not session.exists():
            return None
        try:
            data = self._read_session_json(session)
            if not isinstance(data, dict):
                return None
            messages = data.get("messages", [])
            for msg in reversed(messages):
                if msg.get("type") == "gemini":
                    return msg.get("content", "").strip()
        except (OSError, json.JSONDecodeError):
            pass
        return None

    def latest_conversations(self, n: int = 1) -> List[Tuple[str, str]]:
        """Get the latest n conversations (question, reply) pairs"""
        session = self._latest_session()
        if not session or not session.exists():
            return []
        try:
            data = self._read_session_json(session)
            if not isinstance(data, dict):
                return []
            messages = data.get("messages", [])
        except (OSError, json.JSONDecodeError):
            return []

        conversations: List[Tuple[str, str]] = []
        pending_question: Optional[str] = None

        for msg in messages:
            msg_type = msg.get("type")
            content = msg.get("content", "")
            if not isinstance(content, str):
                content = str(content)
            content = content.strip()

            if msg_type == "user":
                pending_question = content
            elif msg_type == "gemini" and content:
                question = pending_question or ""
                conversations.append((question, content))
                pending_question = None

        return conversations[-n:] if len(conversations) > n else conversations

    def _read_since(self, state: Dict[str, Any], timeout: float, block: bool) -> Tuple[Optional[str], Dict[str, Any]]:
        deadline = time.time() + timeout
        prev_count = state.get("msg_count", 0)
        unknown_baseline = isinstance(prev_count, int) and prev_count < 0
        prev_mtime = state.get("mtime", 0.0)
        prev_mtime_ns = state.get("mtime_ns")
        if prev_mtime_ns is None:
            prev_mtime_ns = int(float(prev_mtime) * 1_000_000_000)
        prev_size = state.get("size", 0)
        prev_session = state.get("session_path")
        prev_last_gemini_id = state.get("last_gemini_id")
        prev_last_gemini_hash = state.get("last_gemini_hash")
        # Allow short timeout to scan new session files (sync tools may use short poll windows)
        rescan_interval = min(2.0, max(0.2, timeout / 2.0))
        last_rescan = time.time()
        last_forced_read = time.time()

        while True:
            # Periodically rescan to detect new session files
            if time.time() - last_rescan >= rescan_interval:
                latest = self._scan_latest_session()
                if latest and latest != self._preferred_session:
                    self._preferred_session = latest
                    # New session file, reset counters
                    if latest != prev_session:
                        prev_count = 0
                        prev_mtime = 0.0
                        prev_size = 0
                        prev_last_gemini_id = None
                        prev_last_gemini_hash = None
                last_rescan = time.time()

            session = self._latest_session()
            if not session or not session.exists():
                if not block:
                    return None, {
                        "session_path": None,
                        "msg_count": 0,
                        "mtime": 0.0,
                        "size": 0,
                        "last_gemini_id": prev_last_gemini_id,
                        "last_gemini_hash": prev_last_gemini_hash,
                    }
                time.sleep(self._poll_interval)
                if time.time() >= deadline:
                    return None, state
                continue

            try:
                stat = session.stat()
                current_mtime = stat.st_mtime
                current_mtime_ns = getattr(stat, "st_mtime_ns", int(current_mtime * 1_000_000_000))
                current_size = stat.st_size
                # On Windows/WSL, mtime may have second-level precision, which can miss rapid writes.
                # Use file size as additional change signal.
                if block and current_mtime_ns <= prev_mtime_ns and current_size == prev_size:
                    if time.time() - last_forced_read < self._force_read_interval:
                        time.sleep(self._poll_interval)
                        if time.time() >= deadline:
                            return None, {
                                "session_path": session,
                                "msg_count": prev_count,
                                "mtime": prev_mtime,
                                "mtime_ns": prev_mtime_ns,
                                "size": prev_size,
                                "last_gemini_id": prev_last_gemini_id,
                                "last_gemini_hash": prev_last_gemini_hash,
                            }
                        continue
                    # fallthrough: forced read

                data = self._read_session_json(session)
                if data is None:
                    raise json.JSONDecodeError("Gemini session JSON is incomplete", "", 0)
                last_forced_read = time.time()
                messages = data.get("messages", [])
                current_count = len(messages)

                if unknown_baseline:
                    # If capture_state couldn't parse the JSON (transient in-place writes), the wait
                    # loop may see a fully-written reply in the first successful read. If we treat
                    # that read as a "baseline" we can miss the reply forever.
                    last_msg = messages[-1] if messages else None
                    if isinstance(last_msg, dict):
                        last_type = last_msg.get("type")
                        last_content = (last_msg.get("content") or "").strip()
                    else:
                        last_type = None
                        last_content = ""

                    # Only fast-path when the file has changed since the baseline stat and the
                    # latest message is a non-empty Gemini reply.
                    if (
                        last_type == "gemini"
                        and last_content
                        and (current_mtime_ns > prev_mtime_ns or current_size != prev_size)
                    ):
                        msg_id = last_msg.get("id") if isinstance(last_msg, dict) else None
                        content_hash = hashlib.sha256(last_content.encode("utf-8")).hexdigest()
                        return last_content, {
                            "session_path": session,
                            "msg_count": current_count,
                            "mtime": current_mtime,
                            "mtime_ns": current_mtime_ns,
                            "size": current_size,
                            "last_gemini_id": msg_id,
                            "last_gemini_hash": content_hash,
                        }

                    prev_mtime = current_mtime
                    prev_mtime_ns = current_mtime_ns
                    prev_size = current_size
                    prev_count = current_count
                    last = self._extract_last_gemini(data)
                    if last:
                        prev_last_gemini_id, content = last
                        prev_last_gemini_hash = hashlib.sha256(content.encode("utf-8")).hexdigest() if content else None
                    unknown_baseline = False
                    if not block:
                        return None, {
                            "session_path": session,
                            "msg_count": prev_count,
                            "mtime": prev_mtime,
                            "mtime_ns": prev_mtime_ns,
                            "size": prev_size,
                            "last_gemini_id": prev_last_gemini_id,
                            "last_gemini_hash": prev_last_gemini_hash,
                        }
                    time.sleep(self._poll_interval)
                    if time.time() >= deadline:
                        return None, {
                            "session_path": session,
                            "msg_count": prev_count,
                            "mtime": prev_mtime,
                            "mtime_ns": prev_mtime_ns,
                            "size": prev_size,
                            "last_gemini_id": prev_last_gemini_id,
                            "last_gemini_hash": prev_last_gemini_hash,
                        }
                    continue

                if current_count > prev_count:
                    # Find the LAST gemini message with content (not the first)
                    # to avoid returning intermediate status messages
                    last_gemini_content = None
                    last_gemini_id = None
                    last_gemini_hash = None
                    for msg in messages[prev_count:]:
                        if msg.get("type") == "gemini":
                            content = msg.get("content", "").strip()
                            if content:
                                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                                msg_id = msg.get("id")
                                if msg_id == prev_last_gemini_id and content_hash == prev_last_gemini_hash:
                                    continue
                                last_gemini_content = content
                                last_gemini_id = msg_id
                                last_gemini_hash = content_hash
                    if last_gemini_content:
                        new_state = {
                            "session_path": session,
                            "msg_count": current_count,
                            "mtime": current_mtime,
                            "mtime_ns": current_mtime_ns,
                            "size": current_size,
                            "last_gemini_id": last_gemini_id,
                            "last_gemini_hash": last_gemini_hash,
                        }
                        return last_gemini_content, new_state
                else:
                    # Some versions write empty gemini message first, then update content in-place.
                    last = self._extract_last_gemini(data)
                    if last:
                        last_id, content = last
                        if content:
                            current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                            if last_id != prev_last_gemini_id or current_hash != prev_last_gemini_hash:
                                new_state = {
                                    "session_path": session,
                                    "msg_count": current_count,
                                    "mtime": current_mtime,
                                    "mtime_ns": current_mtime_ns,
                                    "size": current_size,
                                    "last_gemini_id": last_id,
                                    "last_gemini_hash": current_hash,
                                }
                                return content, new_state

                prev_mtime = current_mtime
                prev_mtime_ns = current_mtime_ns
                prev_count = current_count
                prev_size = current_size
                last = self._extract_last_gemini(data)
                if last:
                    prev_last_gemini_id, content = last
                    prev_last_gemini_hash = hashlib.sha256(content.encode("utf-8")).hexdigest() if content else prev_last_gemini_hash

            except (OSError, json.JSONDecodeError):
                pass

            if not block:
                return None, {
                    "session_path": session,
                    "msg_count": prev_count,
                    "mtime": prev_mtime,
                    "mtime_ns": prev_mtime_ns,
                    "size": prev_size,
                    "last_gemini_id": prev_last_gemini_id,
                    "last_gemini_hash": prev_last_gemini_hash,
                }

            time.sleep(self._poll_interval)
            if time.time() >= deadline:
                return None, {
                    "session_path": session,
                    "msg_count": prev_count,
                    "mtime": prev_mtime,
                    "mtime_ns": prev_mtime_ns,
                    "size": prev_size,
                    "last_gemini_id": prev_last_gemini_id,
                    "last_gemini_hash": prev_last_gemini_hash,
                }

    @staticmethod
    def _extract_last_gemini(payload: dict) -> Optional[Tuple[Optional[str], str]]:
        messages = payload.get("messages", []) if isinstance(payload, dict) else []
        if not isinstance(messages, list):
            return None
        for msg in reversed(messages):
            if not isinstance(msg, dict):
                continue
            if msg.get("type") != "gemini":
                continue
            content = msg.get("content", "")
            if not isinstance(content, str):
                content = str(content)
            return msg.get("id"), content.strip()
        return None


class GeminiCommunicator:
    """Communicate with Gemini via terminal and read replies from session files"""

    def __init__(self, lazy_init: bool = False):
        self.session_info = self._load_session_info()
        if not self.session_info:
            raise RuntimeError("❌ No active Gemini session found, please run ccb gemini (or add gemini to ccb.config) first")

        self.session_id = self.session_info["session_id"]
        self.runtime_dir = Path(self.session_info["runtime_dir"])
        self.terminal = self.session_info.get("terminal", "tmux")
        self.pane_id = get_pane_id_from_session(self.session_info)
        self.pane_title_marker = self.session_info.get("pane_title_marker") or ""
        self.timeout = int(os.environ.get("GEMINI_SYNC_TIMEOUT", "60"))
        self.marker_prefix = "ask"
        self.project_session_file = self.session_info.get("_session_file")
        self.backend = get_backend_for_session(self.session_info)

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
                        "gemini": {
                            "pane_id": self.pane_id or None,
                            "pane_title_marker": self.session_info.get("pane_title_marker"),
                            "session_file": self.project_session_file,
                            "gemini_session_id": self.session_info.get("gemini_session_id"),
                            "gemini_session_path": self.session_info.get("gemini_session_path") or self.session_info.get("session_path"),
                        }
                    },
                }
            )
        except Exception:
            pass

        # Lazy initialization: defer log reader and health check
        self._log_reader: Optional[GeminiLogReader] = None
        self._log_reader_primed = False

        if self.terminal == "wezterm" and self.backend and self.pane_title_marker:
            resolver = getattr(self.backend, "find_pane_by_title_marker", None)
            if callable(resolver):
                resolved = resolver(self.pane_title_marker)
                if resolved:
                    self.pane_id = resolved

        if not lazy_init:
            self._ensure_log_reader()
            healthy, msg = self._check_session_health()
            if not healthy:
                raise RuntimeError(f"❌ Session unhealthy: {msg}\nHint: Please run ccb gemini (or add gemini to ccb.config)")

    @property
    def log_reader(self) -> GeminiLogReader:
        """Lazy-load log reader on first access"""
        if self._log_reader is None:
            self._ensure_log_reader()
        return self._log_reader

    def _ensure_log_reader(self) -> None:
        """Initialize log reader if not already done"""
        if self._log_reader is not None:
            return
        work_dir_hint = self.session_info.get("work_dir")
        log_work_dir = Path(work_dir_hint) if isinstance(work_dir_hint, str) and work_dir_hint else None
        self._log_reader = GeminiLogReader(work_dir=log_work_dir)
        preferred_session = self.session_info.get("gemini_session_path") or self.session_info.get("session_path")
        if preferred_session:
            self._log_reader.set_preferred_session(Path(str(preferred_session)))
        if not self._log_reader_primed:
            self._prime_log_binding()
            self._log_reader_primed = True

    def _find_session_file(self) -> Optional[Path]:
        env_session = (os.environ.get("CCB_SESSION_FILE") or "").strip()
        if env_session:
            try:
                session_path = Path(os.path.expanduser(env_session))
                if session_path.name == ".gemini-session" and session_path.is_file():
                    return session_path
            except Exception:
                pass
        return find_project_session_file(Path.cwd(), ".gemini-session")

    def _prime_log_binding(self) -> None:
        session_path = self.log_reader.current_session_path()
        if not session_path:
            return
        self._remember_gemini_session(session_path)

    def _load_session_info(self):
        if "GEMINI_SESSION_ID" in os.environ:
            terminal = os.environ.get("GEMINI_TERMINAL", "tmux")
            # Get correct pane_id based on terminal type
            if terminal == "wezterm":
                pane_id = os.environ.get("GEMINI_WEZTERM_PANE", "")
            else:
                pane_id = ""
            result = {
                "session_id": os.environ["GEMINI_SESSION_ID"],
                "runtime_dir": os.environ["GEMINI_RUNTIME_DIR"],
                "terminal": terminal,
                "tmux_session": os.environ.get("GEMINI_TMUX_SESSION", ""),
                "pane_id": pane_id,
                "_session_file": None,
            }
            session_file = self._find_session_file()
            if session_file:
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        file_data = json.load(f)
                    if isinstance(file_data, dict):
                        result["gemini_session_path"] = file_data.get("gemini_session_path")
                        result["_session_file"] = str(session_file)
                        # Fix: also read pane_id from session file for tmux
                        if not result["pane_id"]:
                            result["pane_id"] = file_data.get("pane_id", "")
                        if not result["tmux_session"]:
                            result["tmux_session"] = file_data.get("tmux_session", "")
                        if not result.get("pane_title_marker"):
                            result["pane_title_marker"] = file_data.get("pane_title_marker", "")
                except Exception:
                    pass
            return result

        project_session = self._find_session_file()
        if not project_session:
            return None

        try:
            with open(project_session, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict) or not data.get("active", False):
                return None

            runtime_dir = Path(data.get("runtime_dir", ""))
            if not runtime_dir.exists():
                return None

            data["_session_file"] = str(project_session)
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
                return False, "Session ID not found"
            if probe_terminal and self.backend:
                pane_alive = self.backend.is_alive(self.pane_id)
                if self.terminal == "wezterm" and self.pane_title_marker and not pane_alive:
                    resolver = getattr(self.backend, "find_pane_by_title_marker", None)
                    if callable(resolver):
                        resolved = resolver(self.pane_title_marker)
                        if resolved:
                            self.pane_id = resolved
                            pane_alive = self.backend.is_alive(self.pane_id)
                if not pane_alive:
                    if self.terminal == "wezterm":
                        err = getattr(self.backend, "last_list_error", None)
                        if err:
                            return False, f"WezTerm CLI error: {err}"
                    return False, f"{self.terminal} session {self.pane_id} not found"
            return True, "Session OK"
        except Exception as exc:
            return False, f"Check failed: {exc}"

    def _send_via_terminal(self, content: str) -> bool:
        if not self.backend or not self.pane_id:
            raise RuntimeError("Terminal session not configured")
        self.backend.send_text(self.pane_id, content)
        return True

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
            print(f"✅ Sent to Gemini")
            print("Hint: Use gpend to view reply")
            return True
        except Exception as exc:
            print(f"❌ Send failed: {exc}")
            return False

    def ask_sync(self, question: str, timeout: Optional[int] = None) -> Optional[str]:
        try:
            healthy, status = self._check_session_health_impl(probe_terminal=False)
            if not healthy:
                raise RuntimeError(f"❌ Session error: {status}")

            print(f"🔔 {t('sending_to', provider='Gemini')}", flush=True)
            self._send_via_terminal(question)
            # Capture state after sending to reduce "question → send" latency.
            state = self.log_reader.capture_state()

            wait_timeout = self.timeout if timeout is None else int(timeout)
            if wait_timeout == 0:
                print(f"⏳ {t('waiting_for_reply', provider='Gemini')}", flush=True)
                start_time = time.time()
                last_hint = 0
                while True:
                    message, new_state = self.log_reader.wait_for_message(state, timeout=30.0)
                    state = new_state if new_state else state
                    session_path = (new_state or {}).get("session_path") if isinstance(new_state, dict) else None
                    if isinstance(session_path, Path):
                        self._remember_gemini_session(session_path)
                    if message:
                        print(f"🤖 {t('reply_from', provider='Gemini')}")
                        print(message)
                        return message
                    elapsed = int(time.time() - start_time)
                    if elapsed >= last_hint + 30:
                        last_hint = elapsed
                        print(f"⏳ Still waiting... ({elapsed}s)")

            print(f"⏳ Waiting for Gemini reply (timeout {wait_timeout}s)...")
            message, new_state = self.log_reader.wait_for_message(state, float(wait_timeout))
            session_path = (new_state or {}).get("session_path") if isinstance(new_state, dict) else None
            if isinstance(session_path, Path):
                self._remember_gemini_session(session_path)
            if message:
                print(f"🤖 {t('reply_from', provider='Gemini')}")
                print(message)
                return message

            print(f"⏰ {t('timeout_no_reply', provider='Gemini')}")
            return None
        except Exception as exc:
            print(f"❌ Sync ask failed: {exc}")
            return None

    def consume_pending(self, display: bool = True, n: int = 1):
        session_path = self.log_reader.current_session_path()
        if isinstance(session_path, Path):
            self._remember_gemini_session(session_path)

        if n > 1:
            conversations = self.log_reader.latest_conversations(n)
            if not conversations:
                if display:
                    print(t('no_reply_available', provider='Gemini'))
                return None
            if display:
                for i, (question, reply) in enumerate(conversations):
                    if question:
                        print(f"Q: {question}")
                    print(f"A: {reply}")
                    if i < len(conversations) - 1:
                        print("---")
            return conversations

        message = self.log_reader.latest_message()
        if not message:
            if display:
                print(t('no_reply_available', provider='Gemini'))
            return None
        if display:
            print(message)
        return message

    def _remember_gemini_session(self, session_path: Path) -> None:
        if not session_path or not self.project_session_file:
            return
        project_file = Path(self.project_session_file)
        if not project_file.exists():
            return

        try:
            with project_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return

        updated = False
        old_path = str(data.get("gemini_session_path") or "").strip()
        old_id = str(data.get("gemini_session_id") or "").strip()
        session_path_str = str(session_path)
        binding_changed = False
        if data.get("gemini_session_path") != session_path_str:
            data["gemini_session_path"] = session_path_str
            updated = True
            binding_changed = True

        try:
            if not (data.get("ccb_project_id") or "").strip():
                wd = data.get("work_dir")
                if isinstance(wd, str) and wd.strip():
                    data["ccb_project_id"] = compute_ccb_project_id(Path(wd.strip()))
                    updated = True
        except Exception:
            pass

        try:
            project_hash = session_path.parent.parent.name
        except Exception:
            project_hash = ""
        if project_hash and data.get("gemini_project_hash") != project_hash:
            data["gemini_project_hash"] = project_hash
            updated = True

        session_id = ""
        try:
            payload = json.loads(session_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("sessionId"), str):
                session_id = payload["sessionId"]
        except Exception:
            session_id = ""
        if session_id and data.get("gemini_session_id") != session_id:
            data["gemini_session_id"] = session_id
            updated = True
            binding_changed = True

        if not updated:
            return

        new_id = str(session_id or "").strip()
        if not new_id and session_path_str:
            try:
                new_id = Path(session_path_str).stem
            except Exception:
                new_id = ""
        if old_id and old_id != new_id:
            data["old_gemini_session_id"] = old_id
        if old_path and (old_path != session_path_str or (old_id and old_id != new_id)):
            data["old_gemini_session_path"] = old_path
        if (old_path or old_id) and binding_changed:
            data["old_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            try:
                from ctx_transfer_utils import maybe_auto_transfer

                old_path_obj = None
                if old_path:
                    try:
                        old_path_obj = Path(old_path).expanduser()
                    except Exception:
                        old_path_obj = None
                wd = data.get("work_dir")
                work_dir = Path(wd) if isinstance(wd, str) and wd else Path.cwd()
                maybe_auto_transfer(
                    provider="gemini",
                    work_dir=work_dir,
                    session_path=old_path_obj,
                    session_id=old_id or None,
                )
            except Exception:
                pass

        tmp_file = project_file.with_suffix(".tmp")
        try:
            with tmp_file.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_file, project_file)
        except PermissionError as e:
            print(f"⚠️  Cannot update {project_file.name}: {e}", file=sys.stderr)
            print(f"💡 Try: sudo chown $USER:$USER {project_file}", file=sys.stderr)
            try:
                if tmp_file.exists():
                    tmp_file.unlink(missing_ok=True)
            except Exception:
                pass
        except Exception as e:
            print(f"⚠️  Failed to update {project_file.name}: {e}", file=sys.stderr)
            try:
                if tmp_file.exists():
                    tmp_file.unlink(missing_ok=True)
            except Exception:
                pass

        # Best-effort: keep registry in sync with the latest binding.
        try:
            wd = data.get("work_dir")
            ccb_pid = str(data.get("ccb_project_id") or "").strip()
            upsert_registry(
                {
                    "ccb_session_id": self.session_id,
                    "ccb_project_id": ccb_pid or None,
                    "work_dir": wd,
                    "terminal": self.terminal,
                    "providers": {
                        "gemini": {
                            "pane_id": self.pane_id or None,
                            "pane_title_marker": data.get("pane_title_marker"),
                            "session_file": str(project_file),
                            "gemini_session_id": data.get("gemini_session_id"),
                            "gemini_session_path": data.get("gemini_session_path"),
                        }
                    },
                }
            )
        except Exception:
            pass

    def ping(self, display: bool = True) -> Tuple[bool, str]:
        healthy, status = self._check_session_health()
        msg = f"✅ Gemini connection OK ({status})" if healthy else f"❌ Gemini connection error: {status}"
        if display:
            print(msg)
        return healthy, msg

    def get_status(self) -> Dict[str, Any]:
        healthy, status = self._check_session_health()
        return {
            "session_id": self.session_id,
            "runtime_dir": str(self.runtime_dir),
            "terminal": self.terminal,
            "pane_id": self.pane_id,
            "healthy": healthy,
            "status": status,
        }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Gemini communication tool")
    parser.add_argument("question", nargs="*", help="Question to send")
    parser.add_argument("--wait", "-w", action="store_true", help="Wait for reply synchronously")
    parser.add_argument("--timeout", type=int, default=60, help="Sync timeout in seconds")
    parser.add_argument("--ping", action="store_true", help="Test connectivity")
    parser.add_argument("--status", action="store_true", help="View status")
    parser.add_argument("--pending", nargs="?", const=1, type=int, metavar="N",
                        help="View pending reply (optionally last N conversations)")

    args = parser.parse_args()

    try:
        comm = GeminiCommunicator()

        if args.ping:
            comm.ping()
        elif args.status:
            status = comm.get_status()
            print("📊 Gemini status:")
            for key, value in status.items():
                print(f"   {key}: {value}")
        elif args.pending is not None:
            comm.consume_pending(n=args.pending)
        elif args.question:
            question_text = " ".join(args.question).strip()
            if not question_text:
                print("❌ Please provide a question")
                return 1
            if args.wait:
                comm.ask_sync(question_text, args.timeout)
            else:
                comm.ask_async(question_text)
        else:
            print("Please provide a question or use --ping/--status/--pending")
            return 1
        return 0
    except Exception as exc:
        print(f"❌ Execution failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
