"""
Codex communication module (log-driven version)
Sends requests via FIFO and parses replies from ~/.codex/sessions logs.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import shlex
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from terminal import get_backend_for_session, get_pane_id_from_session
from ccb_config import apply_backend_env
from i18n import t
from pane_registry import upsert_registry, registry_path_for_session, load_registry_by_session_id
from session_utils import find_project_session_file
from project_id import compute_ccb_project_id

apply_backend_env()

SESSION_ROOT = Path(os.environ.get("CODEX_SESSION_ROOT") or (Path.home() / ".codex" / "sessions")).expanduser()
SESSION_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value


class CodexLogReader:
    """Reads Codex official logs from ~/.codex/sessions"""

    def __init__(self, root: Path = SESSION_ROOT, log_path: Optional[Path] = None,
                 session_id_filter: Optional[str] = None, work_dir: Optional[Path] = None):
        self.root = Path(root).expanduser()
        self._preferred_log = self._normalize_path(log_path)
        self._session_id_filter = session_id_filter
        self._work_dir = self._normalize_work_dir(work_dir)
        try:
            poll = float(os.environ.get("CODEX_POLL_INTERVAL", "0.05"))
        except Exception:
            poll = 0.05
        self._poll_interval = min(0.5, max(0.01, poll))

    @staticmethod
    def _debug_enabled() -> bool:
        return os.environ.get("CCB_DEBUG") in ("1", "true", "yes") or os.environ.get("CPEND_DEBUG") in (
            "1",
            "true",
            "yes",
        )

    @classmethod
    def _debug(cls, message: str) -> None:
        if not cls._debug_enabled():
            return
        print(f"[DEBUG] {message}", file=sys.stderr)

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        raw = os.environ.get(name)
        if raw is None or raw == "":
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    def _iter_lines_reverse(self, log_path: Path, *, max_bytes: int, max_lines: int) -> List[str]:
        """
        Read lines from the end of a file (reverse order), bounded by max_bytes/max_lines.
        Returns a list in reverse chronological order (last line first).
        """
        if max_bytes <= 0 or max_lines <= 0:
            return []

        try:
            with log_path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                position = handle.tell()
                bytes_read = 0
                lines: List[str] = []
                buffer = b""

                while position > 0 and bytes_read < max_bytes and len(lines) < max_lines:
                    remaining = max_bytes - bytes_read
                    read_size = min(8192, position, remaining)
                    position -= read_size
                    handle.seek(position, os.SEEK_SET)
                    chunk = handle.read(read_size)
                    bytes_read += len(chunk)
                    buffer = chunk + buffer

                    parts = buffer.split(b"\n")
                    buffer = parts[0]
                    for part in reversed(parts[1:]):
                        if len(lines) >= max_lines:
                            break
                        text = part.decode("utf-8", errors="ignore").strip()
                        if text:
                            lines.append(text)

                if position == 0 and buffer and len(lines) < max_lines:
                    text = buffer.decode("utf-8", errors="ignore").strip()
                    if text:
                        lines.append(text)

                return lines
        except OSError as exc:
            self._debug(f"Failed reading log tail: {log_path} ({exc})")
            return []

    def set_preferred_log(self, log_path: Optional[Path]) -> None:
        self._preferred_log = self._normalize_path(log_path)

    def _normalize_work_dir(self, work_dir: Optional[Path]) -> Optional[str]:
        """Normalize work_dir for comparison with cwd in session logs"""
        if work_dir is None:
            work_dir = Path.cwd()
        try:
            return str(work_dir.resolve()).lower()
        except Exception:
            return None

    def _extract_cwd_from_log(self, log_path: Path) -> Optional[str]:
        """Extract cwd from session_meta in the first line of log file"""
        try:
            with log_path.open("r", encoding="utf-8") as f:
                first_line = f.readline()
            if not first_line:
                return None
            entry = json.loads(first_line)
            if entry.get("type") == "session_meta":
                cwd = entry.get("payload", {}).get("cwd")
                if cwd:
                    return str(Path(cwd).resolve()).lower()
        except Exception:
            pass
        return None

    def _normalize_path(self, value: Optional[Any]) -> Optional[Path]:
        if value in (None, ""):
            return None
        if isinstance(value, Path):
            return value
        try:
            return Path(value).expanduser()
        except TypeError:
            return None

    def _scan_latest(self) -> Optional[Path]:
        if not self.root.exists():
            return None
        try:
            # Avoid sorting the full list (can be slow on large histories / slow filesystems).
            latest: Optional[Path] = None
            latest_mtime = -1.0
            for p in (p for p in self.root.glob("**/*.jsonl") if p.is_file()):
                if self._session_id_filter:
                    try:
                        if str(self._session_id_filter).lower() not in str(p).lower():
                            continue
                    except Exception:
                        pass
                if self._work_dir:
                    cwd = self._extract_cwd_from_log(p)
                    if not cwd or cwd != self._work_dir:
                        continue
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest = p
                    latest_mtime = mtime
        except OSError:
            return None

        return latest

    def _latest_log(self) -> Optional[Path]:
        preferred = self._preferred_log
        if preferred and preferred.exists():
            # If we're bound to a specific session id, prefer that log without cross-session scanning.
            if self._session_id_filter:
                self._debug(f"Using preferred log (bound): {preferred}")
                return preferred

            # Otherwise, keep following the most recently updated log for this work dir.
            latest = self._scan_latest()
            if latest and latest != preferred:
                try:
                    preferred_mtime = preferred.stat().st_mtime
                    latest_mtime = latest.stat().st_mtime
                    if latest_mtime > preferred_mtime:
                        self._preferred_log = latest
                        self._debug(f"Preferred log stale; switching to latest: {latest}")
                        return latest
                except OSError:
                    self._preferred_log = latest
                    self._debug(f"Preferred log stat failed; switching to latest: {latest}")
                    return latest
            self._debug(f"Using preferred log: {preferred}")
            return preferred

        self._debug("No valid preferred log, scanning...")
        latest = self._scan_latest()
        if latest:
            self._preferred_log = latest
            self._debug(f"Scan found: {latest}")
            return latest
        return None

    def current_log_path(self) -> Optional[Path]:
        return self._latest_log()

    def capture_state(self) -> Dict[str, Any]:
        """Capture current log path and offset"""
        log = self._latest_log()
        offset = -1
        if log and log.exists():
            try:
                offset = log.stat().st_size
            except OSError:
                try:
                    with log.open("rb") as handle:
                        handle.seek(0, os.SEEK_END)
                        offset = handle.tell()
                except OSError:
                    offset = -1
        return {"log_path": log, "offset": offset}

    def wait_for_message(self, state: Dict[str, Any], timeout: float) -> Tuple[Optional[str], Dict[str, Any]]:
        """Block and wait for new reply"""
        return self._read_since(state, timeout, block=True)

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        """Non-blocking read for reply"""
        return self._read_since(state, timeout=0.0, block=False)

    def wait_for_event(self, state: Dict[str, Any], timeout: float) -> Tuple[Optional[Tuple[str, str]], Dict[str, Any]]:
        """
        Block and wait for a new event.

        Returns:
            ((role, text), new_state) or (None, state) on timeout.
        """
        return self._read_event_since(state, timeout, block=True)

    def try_get_event(self, state: Dict[str, Any]) -> Tuple[Optional[Tuple[str, str]], Dict[str, Any]]:
        """Non-blocking read for an event."""
        return self._read_event_since(state, timeout=0.0, block=False)

    def latest_message(self) -> Optional[str]:
        """Get the latest reply directly"""
        # Always use _latest_log() to detect newer sessions
        log_path = self._latest_log()
        if not log_path or not log_path.exists():
            return None
        tail_bytes = self._env_int("CODEX_LOG_TAIL_BYTES", 1024 * 1024 * 8)
        tail_lines = self._env_int("CODEX_LOG_TAIL_LINES", 5000)
        lines = self._iter_lines_reverse(log_path, max_bytes=tail_bytes, max_lines=tail_lines)
        if not lines:
            return None

        for line in lines:
            if not line.startswith("{"):
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = self._extract_message(entry)
            if message:
                return message
        self._debug(f"No reply found in tail (bytes={tail_bytes}, lines={tail_lines}) for log: {log_path}")
        return None

    def _read_since(self, state: Dict[str, Any], timeout: float, block: bool) -> Tuple[Optional[str], Dict[str, Any]]:
        deadline = time.time() + timeout
        current_path = self._normalize_path(state.get("log_path"))
        offset = state.get("offset", -1)
        if not isinstance(offset, int):
            offset = -1
        # Keep rescans infrequent; new messages usually append to the same log file.
        rescan_interval = min(2.0, max(0.2, timeout / 2.0))
        last_rescan = time.time()

        def ensure_log() -> Path:
            candidates = [
                self._preferred_log if self._preferred_log and self._preferred_log.exists() else None,
                current_path if current_path and current_path.exists() else None,
            ]
            for candidate in candidates:
                if candidate:
                    return candidate
            latest = self._scan_latest()
            if latest:
                self._preferred_log = latest
                return latest
            raise FileNotFoundError("Codex session log not found")

        while True:
            try:
                log_path = ensure_log()
            except FileNotFoundError:
                if not block:
                    return None, {"log_path": None, "offset": 0}
                time.sleep(self._poll_interval)
                continue

            try:
                size = log_path.stat().st_size
            except OSError:
                size = None

            # If caller couldn't capture a baseline, establish it now (start from EOF).
            if offset < 0:
                offset = size if isinstance(size, int) else 0

            with log_path.open("rb") as fh:
                try:
                    if isinstance(size, int) and offset > size:
                        offset = size
                    fh.seek(offset, os.SEEK_SET)
                except OSError:
                    # If seek fails, reset to EOF and try again on next loop.
                    offset = size if isinstance(size, int) else 0
                    if not block:
                        return None, {"log_path": log_path, "offset": offset}
                    time.sleep(self._poll_interval)
                    continue
                while True:
                    if block and time.time() >= deadline:
                        return None, {"log_path": log_path, "offset": offset}
                    pos_before = fh.tell()
                    raw_line = fh.readline()
                    if not raw_line:
                        break
                    # If we hit EOF without a newline, the writer may still be appending this line.
                    if not raw_line.endswith(b"\n"):
                        fh.seek(pos_before)
                        break
                    offset = fh.tell()
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    message = self._extract_message(entry)
                    if message is not None:
                        return message, {"log_path": log_path, "offset": offset}

            if time.time() - last_rescan >= rescan_interval:
                latest = self._scan_latest()
                if latest and latest != log_path:
                    current_path = latest
                    self._preferred_log = latest
                    # When switching to a new log file (session rotation / new session),
                    # start from the beginning to avoid missing a reply that was already written
                    # before we noticed the new file.
                    offset = 0
                    if not block:
                        return None, {"log_path": current_path, "offset": offset}
                    time.sleep(self._poll_interval)
                    last_rescan = time.time()
                    continue
                last_rescan = time.time()

            if not block:
                return None, {"log_path": log_path, "offset": offset}

            time.sleep(self._poll_interval)
            if time.time() >= deadline:
                return None, {"log_path": log_path, "offset": offset}

    def _read_event_since(self, state: Dict[str, Any], timeout: float, block: bool) -> Tuple[Optional[Tuple[str, str]], Dict[str, Any]]:
        """
        Like _read_since(), but returns structured (role, text) events.

        Role is one of: "user", "assistant".
        """
        deadline = time.time() + timeout
        current_path = self._normalize_path(state.get("log_path"))
        offset = state.get("offset", -1)
        if not isinstance(offset, int):
            offset = -1
        rescan_interval = min(2.0, max(0.2, timeout / 2.0))
        last_rescan = time.time()

        def ensure_log() -> Path:
            candidates = [
                self._preferred_log if self._preferred_log and self._preferred_log.exists() else None,
                current_path if current_path and current_path.exists() else None,
            ]
            for candidate in candidates:
                if candidate:
                    return candidate
            latest = self._scan_latest()
            if latest:
                self._preferred_log = latest
                return latest
            raise FileNotFoundError("Codex session log not found")

        while True:
            try:
                log_path = ensure_log()
            except FileNotFoundError:
                if not block:
                    return None, {"log_path": None, "offset": 0}
                time.sleep(self._poll_interval)
                if time.time() >= deadline:
                    return None, {"log_path": None, "offset": 0}
                continue

            try:
                size = log_path.stat().st_size
            except OSError:
                size = None

            if offset < 0:
                offset = size if isinstance(size, int) else 0

            with log_path.open("rb") as fh:
                try:
                    if isinstance(size, int) and offset > size:
                        offset = size
                    fh.seek(offset, os.SEEK_SET)
                except OSError:
                    offset = size if isinstance(size, int) else 0
                    if not block:
                        return None, {"log_path": log_path, "offset": offset}
                    time.sleep(self._poll_interval)
                    continue
                while True:
                    if block and time.time() >= deadline:
                        return None, {"log_path": log_path, "offset": offset}
                    pos_before = fh.tell()
                    raw_line = fh.readline()
                    if not raw_line:
                        break
                    if not raw_line.endswith(b"\n"):
                        fh.seek(pos_before)
                        break
                    offset = fh.tell()
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    event = self._extract_event(entry)
                    if event is not None:
                        return event, {"log_path": log_path, "offset": offset}

            if time.time() - last_rescan >= rescan_interval:
                latest = self._scan_latest()
                if latest and latest != log_path:
                    current_path = latest
                    self._preferred_log = latest
                    offset = 0
                    if not block:
                        return None, {"log_path": current_path, "offset": offset}
                    time.sleep(self._poll_interval)
                    last_rescan = time.time()
                    continue
                last_rescan = time.time()

            if not block:
                return None, {"log_path": log_path, "offset": offset}

            time.sleep(self._poll_interval)
            if time.time() >= deadline:
                return None, {"log_path": log_path, "offset": offset}

    @staticmethod
    def _extract_message(entry: dict) -> Optional[str]:
        entry_type = entry.get("type")
        payload = entry.get("payload", {})

        if entry_type == "response_item":
            if payload.get("type") != "message":
                return None
            if payload.get("role") == "user":
                return None

            content = payload.get("content") or []
            if isinstance(content, list):
                texts: List[str] = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") in ("output_text", "text"):
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            texts.append(text.strip())
                if texts:
                    return "\n".join(texts).strip()
            elif isinstance(content, str) and content.strip():
                return content.strip()

            message = payload.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
            return None

        if entry_type == "event_msg":
            payload_type = payload.get("type")
            if payload_type in ("agent_message", "assistant_message", "assistant", "assistant_response", "message"):
                if payload.get("role") == "user":
                    return None
                msg = payload.get("message") or payload.get("content") or payload.get("text")
                if isinstance(msg, str) and msg.strip():
                    return msg.strip()
            return None

        # Fallback: some Codex builds may emit assistant messages with a role field but different entry types.
        if payload.get("role") == "assistant":
            msg = payload.get("message") or payload.get("content") or payload.get("text")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()
        return None

    @staticmethod
    def _extract_user_message(entry: dict) -> Optional[str]:
        """Extract user question from a JSONL entry"""
        entry_type = entry.get("type")
        payload = entry.get("payload", {})

        if entry_type == "event_msg" and payload.get("type") == "user_message":
            msg = payload.get("message", "")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()

        if entry_type == "response_item":
            if payload.get("type") == "message" and payload.get("role") == "user":
                content = payload.get("content") or []
                texts = [item.get("text", "") for item in content if item.get("type") == "input_text"]
                if texts:
                    return "\n".join(filter(None, texts)).strip()
        return None

    @classmethod
    def _extract_event(cls, entry: dict) -> Optional[Tuple[str, str]]:
        """
        Extract a (role, text) event from a JSONL entry.
        Role is "user" or "assistant".
        """
        user_msg = cls._extract_user_message(entry)
        if isinstance(user_msg, str) and user_msg.strip():
            return "user", user_msg.strip()
        ai_msg = cls._extract_message(entry)
        if isinstance(ai_msg, str) and ai_msg.strip():
            return "assistant", ai_msg.strip()
        return None

    def latest_conversations(self, n: int = 1) -> List[Tuple[str, str]]:
        """Get the latest n conversations (question, reply) pairs"""
        # Always use _latest_log() to detect newer sessions
        log_path = self._latest_log()
        if not log_path or not log_path.exists():
            return []
        if n <= 0:
            return []

        tail_bytes = self._env_int("CODEX_LOG_CONV_TAIL_BYTES", 1024 * 1024 * 32)
        tail_lines = self._env_int("CODEX_LOG_CONV_TAIL_LINES", 20000)
        lines = self._iter_lines_reverse(log_path, max_bytes=tail_bytes, max_lines=tail_lines)
        if not lines:
            return []

        pairs_rev: List[Tuple[str, str]] = []
        pending_reply: Optional[str] = None

        for line in lines:
            if not line.startswith("{"):
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if pending_reply is None:
                ai_msg = self._extract_message(entry)
                if ai_msg:
                    pending_reply = ai_msg
                continue

            user_msg = self._extract_user_message(entry)
            if user_msg:
                pairs_rev.append((user_msg, pending_reply))
                pending_reply = None
                if len(pairs_rev) >= n:
                    break

        pairs = list(reversed(pairs_rev))
        if not pairs:
            self._debug(f"No conversations found in tail (bytes={tail_bytes}, lines={tail_lines}) for log: {log_path}")
        return pairs


class CodexCommunicator:
    """Communicates with Codex bridge via FIFO and reads replies from logs"""

    def __init__(self, lazy_init: bool = False):
        self.session_info = self._load_session_info()
        if not self.session_info:
            raise RuntimeError("❌ No active Codex session found. Run 'ccb codex' (or add codex to ccb.config) first")

        self.session_id = self.session_info["session_id"]
        self.runtime_dir = Path(self.session_info["runtime_dir"])
        self.input_fifo = Path(self.session_info["input_fifo"])
        self.terminal = self.session_info.get("terminal", os.environ.get("CODEX_TERMINAL", "tmux"))
        self.pane_id = get_pane_id_from_session(self.session_info) or ""
        self.pane_title_marker = self.session_info.get("pane_title_marker") or ""
        self.backend = get_backend_for_session(self.session_info)

        self.timeout = int(os.environ.get("CODEX_SYNC_TIMEOUT", "30"))
        self.marker_prefix = "ask"
        self.project_session_file = self.session_info.get("_session_file")
        self._pane_health_cache: Optional[Tuple[float, bool]] = None
        self._pane_health_ttl = max(0.0, _env_float("CCB_CODEX_PANE_HEALTH_TTL", 1.0))

        # Lazy initialization: defer log reader and health check
        self._log_reader: Optional[CodexLogReader] = None
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
                raise RuntimeError(f"❌ Session unhealthy: {msg}\nTip: Run 'ccb codex' (or add codex to ccb.config) to start a new session")

    @property
    def log_reader(self) -> CodexLogReader:
        """Lazy-load log reader on first access"""
        if self._log_reader is None:
            self._ensure_log_reader()
        return self._log_reader

    def _ensure_log_reader(self) -> None:
        """Initialize log reader if not already done"""
        if self._log_reader is not None:
            return
        preferred_log = self.session_info.get("codex_session_path")
        bound_session_id = self.session_info.get("codex_session_id")
        self._log_reader = CodexLogReader(log_path=preferred_log, session_id_filter=bound_session_id)
        if not self._log_reader_primed:
            self._prime_log_binding()
            self._log_reader_primed = True

    def _find_session_file(self) -> Optional[Path]:
        env_session = (os.environ.get("CCB_SESSION_FILE") or "").strip()
        if env_session:
            try:
                session_path = Path(os.path.expanduser(env_session))
                if session_path.name == ".codex-session" and session_path.is_file():
                    return session_path
            except Exception:
                pass
        return find_project_session_file(Path.cwd(), ".codex-session")

    def _load_session_info(self):
        if "CODEX_SESSION_ID" in os.environ:
            terminal = os.environ.get("CODEX_TERMINAL", "tmux")
            # Get pane_id based on terminal type
            if terminal == "wezterm":
                pane_id = os.environ.get("CODEX_WEZTERM_PANE", "")
            else:
                pane_id = ""
            result = {
                "session_id": os.environ["CODEX_SESSION_ID"],
                "runtime_dir": os.environ["CODEX_RUNTIME_DIR"],
                "input_fifo": os.environ["CODEX_INPUT_FIFO"],
                "output_fifo": os.environ.get("CODEX_OUTPUT_FIFO", ""),
                "terminal": terminal,
                "tmux_session": os.environ.get("CODEX_TMUX_SESSION", ""),
                "pane_id": pane_id,
                "_session_file": None,
            }
            session_file = self._find_session_file()
            if session_file:
                try:
                    with open(session_file, "r", encoding="utf-8-sig") as f:
                        file_data = json.load(f)
                    if isinstance(file_data, dict):
                        result["codex_session_path"] = file_data.get("codex_session_path")
                        result["codex_session_id"] = file_data.get("codex_session_id")
                        result["_session_file"] = str(session_file)
                except Exception:
                    pass
            registry = load_registry_by_session_id(os.environ["CODEX_SESSION_ID"])
            if isinstance(registry, dict):
                reg_log = registry.get("codex_session_path")
                reg_id = registry.get("codex_session_id")
                if reg_log:
                    result["codex_session_path"] = reg_log
                if reg_id:
                    result["codex_session_id"] = reg_id
            return result

        project_session = self._find_session_file()
        if not project_session:
            return None

        try:
            with open(project_session, "r", encoding="utf-8-sig") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                return None

            if not data.get("active", False):
                return None

            runtime_dir = Path(data.get("runtime_dir", ""))
            if not runtime_dir.exists():
                return None

            data["_session_file"] = str(project_session)
            return data

        except Exception:
            return None

    def _prime_log_binding(self) -> None:
        """Ensure log path and session ID are bound early at session start"""
        log_hint = self.log_reader.current_log_path()
        if not log_hint:
            return
        self._remember_codex_session(log_hint)

    def _check_session_health(self):
        return self._check_session_health_impl(probe_terminal=True)

    def _check_session_health_impl(self, probe_terminal: bool):
        try:
            if not self.runtime_dir.exists():
                return False, "Runtime directory does not exist"

            # WezTerm mode: no tmux wrapper, so codex.pid usually not generated;
            # use pane liveness as health check (consistent with Gemini logic).
            if self.terminal == "wezterm":
                if not self.pane_id:
                    return False, f"{self.terminal} pane_id not found"
                pane_alive = self._pane_alive(force=False)
                if self.terminal == "wezterm" and self.backend and self.pane_title_marker:
                    resolver = getattr(self.backend, "find_pane_by_title_marker", None)
                    if callable(resolver) and (not pane_alive):
                        resolved = resolver(self.pane_title_marker)
                        if resolved:
                            self.pane_id = resolved
                            self._invalidate_pane_health_cache()
                            pane_alive = self._pane_alive(force=True)
                if probe_terminal and not pane_alive:
                    return False, f"{self.terminal} pane does not exist: {self.pane_id}"
                return True, "Session healthy"

            # tmux mode: relies on wrapper to write codex.pid and FIFO
            codex_pid_file = self.runtime_dir / "codex.pid"
            if not codex_pid_file.exists():
                return False, "Codex process PID file not found"

            with open(codex_pid_file, "r", encoding="utf-8") as f:
                codex_pid = int(f.read().strip())
            try:
                os.kill(codex_pid, 0)
            except PermissionError:
                # 沙箱阻止了 os.kill，使用 ps 命令验证
                import subprocess
                try:
                    result = subprocess.run(["ps", "-p", str(codex_pid)], capture_output=True, timeout=2)
                    if result.returncode != 0:
                        return False, f"Codex process (PID:{codex_pid}) has exited"
                except Exception:
                    pass  # 无法验证，假设存在
            except OSError:
                return False, f"Codex process (PID:{codex_pid}) has exited"

            bridge_pid_file = self.runtime_dir / "bridge.pid"
            if not bridge_pid_file.exists():
                return False, "Bridge process PID file not found"
            try:
                with bridge_pid_file.open("r", encoding="utf-8") as handle:
                    bridge_pid = int(handle.read().strip())
            except Exception:
                return False, "Failed to read bridge process PID"
            try:
                os.kill(bridge_pid, 0)
            except PermissionError:
                # 沙箱阻止了 os.kill，使用 ps 命令验证
                import subprocess
                try:
                    result = subprocess.run(["ps", "-p", str(bridge_pid)], capture_output=True, timeout=2)
                    if result.returncode != 0:
                        return False, f"Bridge process (PID:{bridge_pid}) has exited"
                except Exception:
                    pass  # 无法验证，假设存在
            except OSError:
                return False, f"Bridge process (PID:{bridge_pid}) has exited"

            if not self.input_fifo.exists():
                return False, "Communication pipe does not exist"

            return True, "Session healthy"
        except Exception as exc:
            return False, f"Health check failed: {exc}"

    def _invalidate_pane_health_cache(self) -> None:
        self._pane_health_cache = None

    def _pane_alive(self, *, force: bool) -> bool:
        ttl = self._pane_health_ttl
        now = time.time()
        if (not force) and ttl > 0 and self._pane_health_cache:
            cached_ts, cached_val = self._pane_health_cache
            if now - cached_ts < ttl:
                return cached_val
        backend = self.backend
        pane_id = self.pane_id
        alive = bool(backend and pane_id and backend.is_alive(pane_id))
        if ttl > 0:
            self._pane_health_cache = (now, alive)
        else:
            self._pane_health_cache = None
        return alive

    def _send_via_terminal(self, content: str) -> None:
        if not self.backend or not self.pane_id:
            raise RuntimeError("Terminal session not configured")
        self.backend.send_text(self.pane_id, content)

    def _send_message(self, content: str) -> Tuple[str, Dict[str, Any]]:
        marker = self._generate_marker()
        message = {
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "marker": marker,
        }

        state = self.log_reader.capture_state()

        # tmux mode drives bridge via FIFO; WezTerm mode injects text directly to pane
        if self.terminal == "wezterm":
            self._send_via_terminal(content)
        else:
            with open(self.input_fifo, "w", encoding="utf-8") as fifo:
                fifo.write(json.dumps(message, ensure_ascii=False) + "\n")
                fifo.flush()

        return marker, state

    def _generate_marker(self) -> str:
        return f"{self.marker_prefix}-{int(time.time())}-{os.getpid()}"

    def ask_async(self, question: str) -> bool:
        try:
            healthy, status = self._check_session_health_impl(probe_terminal=False)
            if not healthy:
                raise RuntimeError(f"❌ Session error: {status}")

            marker, state = self._send_message(question)
            log_hint = state.get("log_path") or self.log_reader.current_log_path()
            self._remember_codex_session(log_hint)
            print(f"✅ Sent to Codex (marker: {marker[:12]}...)")
            print("Tip: Use /cpend to view latest reply")
            return True
        except Exception as exc:
            print(f"❌ Send failed: {exc}")
            return False

    def ask_sync(self, question: str, timeout: Optional[int] = None) -> Optional[str]:
        try:
            healthy, status = self._check_session_health_impl(probe_terminal=False)
            if not healthy:
                raise RuntimeError(f"❌ Session error: {status}")

            print(f"🔔 {t('sending_to', provider='Codex')}", flush=True)
            marker, state = self._send_message(question)
            wait_timeout = self.timeout if timeout is None else int(timeout)
            if wait_timeout == 0:
                print(f"⏳ {t('waiting_for_reply', provider='Codex')}", flush=True)
                start_time = time.time()
                last_hint = 0
                while True:
                    message, new_state = self.log_reader.wait_for_message(state, timeout=30.0)
                    state = new_state or state
                    log_hint = (new_state or {}).get("log_path") if isinstance(new_state, dict) else None
                    if not log_hint:
                        log_hint = self.log_reader.current_log_path()
                    self._remember_codex_session(log_hint)
                    if message:
                        print(f"🤖 {t('reply_from', provider='Codex')}")
                        print(message)
                        return message
                    elapsed = int(time.time() - start_time)
                    if elapsed >= last_hint + 30:
                        last_hint = elapsed
                        print(f"⏳ Still waiting... ({elapsed}s)")

            print(f"⏳ Waiting for Codex reply (timeout {wait_timeout}s)...")
            message, new_state = self.log_reader.wait_for_message(state, float(wait_timeout))
            log_hint = (new_state or {}).get("log_path") if isinstance(new_state, dict) else None
            if not log_hint:
                log_hint = self.log_reader.current_log_path()
            self._remember_codex_session(log_hint)
            if message:
                print(f"🤖 {t('reply_from', provider='Codex')}")
                print(message)
                return message

            print(f"⏰ {t('timeout_no_reply', provider='Codex')}")
            return None
        except Exception as exc:
            print(f"❌ Sync ask failed: {exc}")
            return None

    def consume_pending(self, display: bool = True, n: int = 1):
        current_path = self.log_reader.current_log_path()
        self._remember_codex_session(current_path)

        if n > 1:
            conversations = self.log_reader.latest_conversations(n)
            if not conversations:
                if display:
                    print(t('no_reply_available', provider='Codex'))
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
        if message:
            self._remember_codex_session(self.log_reader.current_log_path())
        if not message:
            if display:
                print(t('no_reply_available', provider='Codex'))
            return None
        if display:
            print(message)
        return message

    def ping(self, display: bool = True) -> Tuple[bool, str]:
        healthy, status = self._check_session_health()
        msg = f"✅ Codex connection OK ({status})" if healthy else f"❌ Codex connection error: {status}"
        if display:
            print(msg)
        return healthy, msg

    def get_status(self) -> Dict[str, Any]:
        healthy, status = self._check_session_health()
        info = {
            "session_id": self.session_id,
            "runtime_dir": str(self.runtime_dir),
            "healthy": healthy,
            "status": status,
            "input_fifo": str(self.input_fifo),
        }

        codex_pid_file = self.runtime_dir / "codex.pid"
        if codex_pid_file.exists():
            with open(codex_pid_file, "r", encoding="utf-8") as f:
                info["codex_pid"] = int(f.read().strip())

        return info

    def _remember_codex_session(self, log_path: Optional[Path]) -> None:
        if not log_path:
            log_path = self.log_reader.current_log_path()
            if not log_path:
                return

        try:
            log_path_obj = log_path if isinstance(log_path, Path) else Path(str(log_path)).expanduser()
        except Exception:
            return

        self.log_reader.set_preferred_log(log_path_obj)

        if not self.project_session_file:
            return

        project_file = Path(self.project_session_file)
        if not project_file.exists():
            return
        try:
            with project_file.open("r", encoding="utf-8-sig") as handle:
                data = json.load(handle)
        except Exception:
            return

        ccb_project_id = ""
        try:
            wd_hint = self.session_info.get("work_dir")
            if isinstance(wd_hint, str) and wd_hint.strip():
                ccb_project_id = compute_ccb_project_id(Path(wd_hint.strip()))
        except Exception:
            ccb_project_id = ""

        path_str = str(log_path_obj)
        session_id = self._extract_session_id(log_path_obj)
        resume_cmd = f"codex resume {session_id}" if session_id else None
        updated = False

        started_at = data.get("started_at")
        if started_at and not data.get("codex_session_path") and not data.get("codex_session_id"):
            try:
                started_ts = time.mktime(time.strptime(started_at, "%Y-%m-%d %H:%M:%S"))
            except Exception:
                started_ts = None
            if started_ts:
                try:
                    log_mtime = log_path_obj.stat().st_mtime
                except OSError:
                    log_mtime = None
                if log_mtime is not None and log_mtime < started_ts:
                    if os.environ.get("CCB_DEBUG") in ("1", "true", "yes"):
                        print(
                            f"[DEBUG] Skip binding log older than session start: {log_path_obj}",
                            file=sys.stderr,
                        )
                    return

        if data.get("codex_session_path") != path_str:
            data["codex_session_path"] = path_str
            updated = True
        if session_id and data.get("codex_session_id") != session_id:
            data["codex_session_id"] = session_id
            updated = True
        if ccb_project_id and data.get("ccb_project_id") != ccb_project_id:
            data["ccb_project_id"] = ccb_project_id
            updated = True
        if resume_cmd:
            if data.get("codex_start_cmd") != resume_cmd:
                data["codex_start_cmd"] = resume_cmd
                updated = True
        elif data.get("codex_start_cmd", "").startswith("codex resume "):
            # keep existing command if we cannot derive a better one
            pass
        if data.get("active") is False:
            data["active"] = True
            updated = True

        if updated:
            tmp_file = project_file.with_suffix(".tmp")
            try:
                with tmp_file.open("w", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False, indent=2)
                os.replace(tmp_file, project_file)
            except PermissionError as e:
                print(f"⚠️  Cannot update {project_file.name}: {e}", file=sys.stderr)
                print(f"💡 Try: sudo chown $USER:$USER {project_file}", file=sys.stderr)
                if tmp_file.exists():
                    tmp_file.unlink(missing_ok=True)
            except Exception as e:
                print(f"⚠️  Failed to update {project_file.name}: {e}", file=sys.stderr)
                if tmp_file.exists():
                    tmp_file.unlink(missing_ok=True)

        registry_path = registry_path_for_session(self.session_id)
        if registry_path.exists():
            ok = upsert_registry(
                {
                    "ccb_session_id": self.session_id,
                    "ccb_project_id": ccb_project_id or None,
                    "work_dir": self.session_info.get("work_dir"),
                    "terminal": self.terminal,
                    "providers": {
                        "codex": {
                            "pane_id": self.pane_id or None,
                            "pane_title_marker": self.pane_title_marker or None,
                            "session_file": self.project_session_file,
                            "codex_session_id": session_id,
                            "codex_session_path": path_str,
                        }
                    },
                    # Legacy duplicates (older tools might read these flat keys).
                    "codex_pane_id": self.pane_id or None,
                    "codex_session_id": session_id,
                    "codex_session_path": path_str,
                }
            )
            if not ok:
                print("⚠️  Failed to update cpend registry", file=sys.stderr)

        self.session_info["codex_session_path"] = path_str
        if session_id:
            self.session_info["codex_session_id"] = session_id
        if resume_cmd:
            self.session_info["codex_start_cmd"] = resume_cmd

    @staticmethod
    def _extract_session_id(log_path: Path) -> Optional[str]:
        for source in (log_path.stem, log_path.name):
            match = SESSION_ID_PATTERN.search(source)
            if match:
                return match.group(0)

        try:
            with log_path.open("r", encoding="utf-8") as handle:
                first_line = handle.readline()
        except OSError:
            return None

        if not first_line:
            return None

        match = SESSION_ID_PATTERN.search(first_line)
        if match:
            return match.group(0)

        try:
            entry = json.loads(first_line)
        except Exception:
            return None

        payload = entry.get("payload", {}) if isinstance(entry, dict) else {}
        candidates = [
            entry.get("session_id") if isinstance(entry, dict) else None,
            payload.get("id") if isinstance(payload, dict) else None,
            payload.get("session", {}).get("id") if isinstance(payload, dict) else None,
        ]
        for candidate in candidates:
            if isinstance(candidate, str):
                match = SESSION_ID_PATTERN.search(candidate)
                if match:
                    return match.group(0)
        return None


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Codex communication tool (log-driven)")
    parser.add_argument("question", nargs="*", help="Question to send")
    parser.add_argument("--wait", "-w", action="store_true", help="Wait for reply synchronously")
    parser.add_argument("--timeout", type=int, default=30, help="Sync timeout in seconds")
    parser.add_argument("--ping", action="store_true", help="Test connectivity")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--pending", nargs="?", const=1, type=int, metavar="N",
                        help="Show pending reply (optionally last N conversations)")

    args = parser.parse_args()

    try:
        comm = CodexCommunicator()

        if args.ping:
            comm.ping()
        elif args.status:
            status = comm.get_status()
            print("📊 Codex status:")
            for key, value in status.items():
                print(f"   {key}: {value}")
        elif args.pending is not None:
            comm.consume_pending(n=args.pending)
        elif args.question:
            tokens = list(args.question)
            if tokens and tokens[0].lower() == "ask":
                tokens = tokens[1:]
            question_text = " ".join(tokens).strip()
            if not question_text:
                print("❌ Please provide a question")
                return 1
            if args.wait:
                comm.ask_sync(question_text, args.timeout)
            else:
                comm.ask_async(question_text)
        else:
            print("Please provide a question or use --ping/--status/--pending options")
            return 1
        return 0
    except Exception as exc:
        print(f"❌ Execution failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
