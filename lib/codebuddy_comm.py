"""
CodeBuddy communication module.

Reads replies from tmux pane-log files (raw terminal text) and sends prompts
by injecting text into the CodeBuddy pane via the configured backend.

Unlike Droid, CodeBuddy does not produce structured JSONL session logs. Instead,
we read raw terminal output captured via `tmux pipe-pane`, strip ANSI escape
sequences, and look for CCB protocol markers in the plain text.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ccb_config import apply_backend_env
from pane_registry import upsert_registry
from project_id import compute_ccb_project_id
from session_utils import find_project_session_file
from terminal import get_backend_for_session, get_pane_id_from_session

apply_backend_env()

# ---------------------------------------------------------------------------
# ANSI escape stripping
# ---------------------------------------------------------------------------

_ANSI_ESCAPE_RE = re.compile(
    r"""
    \x1b          # ESC
    (?:           # followed by one of …
      \[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]   # CSI sequence
    | \].*?(?:\x07|\x1b\\)                       # OSC sequence (terminated by BEL or ST)
    | [\x40-\x5f]                                 # Fe sequence (2-byte)
    )
    """,
    re.VERBOSE,
)


def _strip_ansi(text: str) -> str:
    """Remove ANSI/VT escape sequences from raw terminal output."""
    return _ANSI_ESCAPE_RE.sub("", text)


# ---------------------------------------------------------------------------
# CCB marker patterns
# ---------------------------------------------------------------------------

_CCB_REQ_ID_RE = re.compile(r"^\s*CCB_REQ_ID:\s*(\S+)\s*$", re.MULTILINE)
_CCB_DONE_RE = re.compile(
    r"^\s*CCB_DONE:\s*(?:[0-9a-f]{32}|\d{8}-\d{6}-\d{3}-\d+-\d+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


# ---------------------------------------------------------------------------
# CodebuddyLogReader — reads from tmux pane-log files
# ---------------------------------------------------------------------------


class CodebuddyLogReader:
    """Reads CodeBuddy replies from tmux pane-log files (raw terminal text)."""

    def __init__(self, work_dir: Optional[Path] = None, pane_log_path: Optional[Path] = None):
        self.work_dir = work_dir or Path.cwd()
        self._pane_log_path: Optional[Path] = pane_log_path
        try:
            poll = float(os.environ.get("CODEBUDDY_POLL_INTERVAL", "0.05"))
        except Exception:
            poll = 0.05
        self._poll_interval = min(0.5, max(0.02, poll))

    def set_pane_log_path(self, path: Optional[Path]) -> None:
        """Override the pane log path (e.g. from session file)."""
        if path:
            try:
                candidate = path if isinstance(path, Path) else Path(str(path)).expanduser()
            except Exception:
                return
            self._pane_log_path = candidate

    def _resolve_log_path(self) -> Optional[Path]:
        """Return the pane log path, or None if unavailable."""
        if self._pane_log_path and self._pane_log_path.exists():
            return self._pane_log_path
        return None

    # ---- public interface identical to DroidLogReader ----

    def capture_state(self) -> Dict[str, Any]:
        log_path = self._resolve_log_path()
        offset = 0
        if log_path and log_path.exists():
            try:
                offset = log_path.stat().st_size
            except OSError:
                offset = 0
        return {"pane_log_path": log_path, "offset": offset}

    def wait_for_message(self, state: Dict[str, Any], timeout: float) -> Tuple[Optional[str], Dict[str, Any]]:
        return self._read_since(state, timeout=timeout, block=True)

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        return self._read_since(state, timeout=0.0, block=False)

    def wait_for_events(self, state: Dict[str, Any], timeout: float) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        return self._read_since_events(state, timeout=timeout, block=True)

    def try_get_events(self, state: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        return self._read_since_events(state, timeout=0.0, block=False)

    def latest_message(self) -> Optional[str]:
        """Scan the full pane log and return the last assistant content block."""
        log_path = self._resolve_log_path()
        if not log_path or not log_path.exists():
            return None
        try:
            raw = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        clean = _strip_ansi(raw)
        blocks = self._extract_assistant_blocks(clean)
        return blocks[-1] if blocks else None

    def latest_conversations(self, n: int = 1) -> List[Tuple[str, str]]:
        """Return up to *n* recent (user_prompt, assistant_reply) pairs from the pane log."""
        log_path = self._resolve_log_path()
        if not log_path or not log_path.exists():
            return []
        try:
            raw = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        clean = _strip_ansi(raw)
        pairs = self._extract_conversation_pairs(clean)
        return pairs[-max(1, int(n)):]

    # ---- internal helpers ----

    def _read_since(self, state: Dict[str, Any], timeout: float, block: bool) -> Tuple[Optional[str], Dict[str, Any]]:
        deadline = time.time() + max(0.0, float(timeout)) if block else time.time()
        current_state = dict(state or {})

        while True:
            log_path = self._resolve_log_path()
            if log_path is None or not log_path.exists():
                if not block or time.time() >= deadline:
                    return None, current_state
                time.sleep(self._poll_interval)
                continue

            # If log path changed, reset offset
            if current_state.get("pane_log_path") != log_path:
                current_state["pane_log_path"] = log_path
                current_state["offset"] = 0

            message, current_state = self._read_new_content(log_path, current_state)
            if message:
                return message, current_state

            if not block or time.time() >= deadline:
                return None, current_state
            time.sleep(self._poll_interval)

    def _read_new_content(self, log_path: Path, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        """Read new bytes from the pane log, strip ANSI, extract assistant replies."""
        offset = int(state.get("offset") or 0)
        try:
            size = log_path.stat().st_size
        except OSError:
            return None, state

        if size < offset:
            # Log was truncated / rotated — reset
            offset = 0

        if size == offset:
            return None, state

        try:
            with log_path.open("rb") as handle:
                handle.seek(offset)
                data = handle.read()
        except OSError:
            return None, state

        new_offset = offset + len(data)
        text = data.decode("utf-8", errors="replace")
        clean = _strip_ansi(text)

        # Look for assistant content blocks in the new chunk
        blocks = self._extract_assistant_blocks(clean)
        latest = blocks[-1] if blocks else None

        new_state = {"pane_log_path": log_path, "offset": new_offset}
        return latest, new_state

    def _read_since_events(self, state: Dict[str, Any], timeout: float, block: bool) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        deadline = time.time() + max(0.0, float(timeout)) if block else time.time()
        current_state = dict(state or {})

        while True:
            log_path = self._resolve_log_path()
            if log_path is None or not log_path.exists():
                if not block or time.time() >= deadline:
                    return [], current_state
                time.sleep(self._poll_interval)
                continue

            if current_state.get("pane_log_path") != log_path:
                current_state["pane_log_path"] = log_path
                current_state["offset"] = 0

            events, current_state = self._read_new_events(log_path, current_state)
            if events:
                return events, current_state

            if not block or time.time() >= deadline:
                return [], current_state
            time.sleep(self._poll_interval)

    def _read_new_events(self, log_path: Path, state: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        offset = int(state.get("offset") or 0)
        try:
            size = log_path.stat().st_size
        except OSError:
            return [], state

        if size < offset:
            offset = 0
        if size == offset:
            return [], state

        try:
            with log_path.open("rb") as handle:
                handle.seek(offset)
                data = handle.read()
        except OSError:
            return [], state

        new_offset = offset + len(data)
        text = data.decode("utf-8", errors="replace")
        clean = _strip_ansi(text)

        events: List[Tuple[str, str]] = []
        pairs = self._extract_conversation_pairs(clean)
        for user_msg, assistant_msg in pairs:
            if user_msg:
                events.append(("user", user_msg))
            if assistant_msg:
                events.append(("assistant", assistant_msg))

        new_state = {"pane_log_path": log_path, "offset": new_offset}
        return events, new_state

    @staticmethod
    def _extract_assistant_blocks(text: str) -> List[str]:
        """
        Extract assistant reply blocks from cleaned terminal text.

        A reply block is text between a CCB_REQ_ID marker and the corresponding
        CCB_DONE marker. If no markers are found, fall back to returning non-empty
        text chunks that look like assistant output.
        """
        blocks: List[str] = []
        req_positions = [(m.end(), m.group(1)) for m in _CCB_REQ_ID_RE.finditer(text)]
        done_positions = [m.start() for m in _CCB_DONE_RE.finditer(text)]

        if not req_positions and not done_positions:
            # No CCB markers — treat the whole text as potential output
            stripped = text.strip()
            if stripped:
                blocks.append(stripped)
            return blocks

        for req_end, _req_id in req_positions:
            # Find the next CCB_DONE after this REQ_ID
            next_done = None
            for dp in done_positions:
                if dp > req_end:
                    next_done = dp
                    break
            if next_done is not None:
                segment = text[req_end:next_done].strip()
                if segment:
                    blocks.append(segment)
            else:
                # No done marker yet — partial reply, take what we have
                segment = text[req_end:].strip()
                if segment:
                    blocks.append(segment)

        return blocks

    @staticmethod
    def _extract_conversation_pairs(text: str) -> List[Tuple[str, str]]:
        """
        Extract (user_prompt, assistant_reply) pairs from terminal text.

        User prompts are the text injected before CCB_REQ_ID markers.
        Assistant replies are the text between CCB_REQ_ID and CCB_DONE.
        """
        pairs: List[Tuple[str, str]] = []
        req_matches = list(_CCB_REQ_ID_RE.finditer(text))
        done_positions = [m.start() for m in _CCB_DONE_RE.finditer(text)]

        prev_end = 0
        for req_match in req_matches:
            # User prompt is text before this REQ_ID line (from previous boundary)
            user_text = text[prev_end:req_match.start()].strip()
            req_end = req_match.end()

            # Find next CCB_DONE
            next_done = None
            for dp in done_positions:
                if dp > req_end:
                    next_done = dp
                    break

            if next_done is not None:
                assistant_text = text[req_end:next_done].strip()
                prev_end = next_done
            else:
                assistant_text = text[req_end:].strip()
                prev_end = len(text)

            pairs.append((user_text, assistant_text))

        return pairs


# ---------------------------------------------------------------------------
# CodebuddyCommunicator — loads session, checks pane health
# ---------------------------------------------------------------------------


class CodebuddyCommunicator:
    """Communicate with CodeBuddy via terminal and read replies from pane logs."""

    def __init__(self, lazy_init: bool = False):
        self.session_info = self._load_session_info()
        if not self.session_info:
            raise RuntimeError(
                "No active CodeBuddy session found. "
                "Run 'ccb codebuddy' (or add codebuddy to ccb.config) first"
            )

        self.session_id = str(self.session_info.get("session_id") or "").strip()
        self.terminal = self.session_info.get("terminal", "tmux")
        self.pane_id = get_pane_id_from_session(self.session_info) or ""
        self.pane_title_marker = self.session_info.get("pane_title_marker") or ""
        self.backend = get_backend_for_session(self.session_info)
        self.timeout = int(
            os.environ.get("CODEBUDDY_SYNC_TIMEOUT", os.environ.get("CCB_SYNC_TIMEOUT", "3600"))
        )
        self.project_session_file = self.session_info.get("_session_file")

        self._log_reader: Optional[CodebuddyLogReader] = None
        self._log_reader_primed = False

        if self.terminal == "wezterm" and self.backend and self.pane_title_marker:
            resolver = getattr(self.backend, "find_pane_by_title_marker", None)
            if callable(resolver):
                resolved = resolver(self.pane_title_marker)
                if resolved:
                    self.pane_id = resolved

        self._publish_registry()

        if not lazy_init:
            self._ensure_log_reader()
            healthy, msg = self._check_session_health()
            if not healthy:
                raise RuntimeError(
                    f"Session unhealthy: {msg}\n"
                    "Hint: run ccb codebuddy (or add codebuddy to ccb.config) to start a new session"
                )

    @property
    def log_reader(self) -> CodebuddyLogReader:
        if self._log_reader is None:
            self._ensure_log_reader()
        assert self._log_reader is not None
        return self._log_reader

    def _ensure_log_reader(self) -> None:
        if self._log_reader is not None:
            return
        work_dir_hint = self.session_info.get("work_dir")
        log_work_dir = Path(work_dir_hint) if isinstance(work_dir_hint, str) and work_dir_hint else None

        # Derive pane log path from session info
        pane_log_path: Optional[Path] = None
        raw_log_path = self.session_info.get("pane_log_path")
        if raw_log_path:
            pane_log_path = Path(str(raw_log_path)).expanduser()
        elif self.session_info.get("runtime_dir"):
            # Convention: runtime_dir / pane.log
            pane_log_path = Path(str(self.session_info["runtime_dir"])) / "pane.log"

        self._log_reader = CodebuddyLogReader(work_dir=log_work_dir, pane_log_path=pane_log_path)
        self._log_reader_primed = True

    def _find_session_file(self) -> Optional[Path]:
        env_session = (os.environ.get("CCB_SESSION_FILE") or "").strip()
        if env_session:
            try:
                session_path = Path(os.path.expanduser(env_session))
                if session_path.name == ".codebuddy-session" and session_path.is_file():
                    return session_path
            except Exception:
                pass
        return find_project_session_file(Path.cwd(), ".codebuddy-session")

    def _load_session_info(self) -> Optional[dict]:
        project_session = self._find_session_file()
        if not project_session:
            return None
        try:
            with project_session.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or data.get("active", False) is False:
                return None
            data["_session_file"] = str(project_session)
            return data
        except Exception:
            return None

    def _publish_registry(self) -> None:
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
                        "codebuddy": {
                            "pane_id": self.pane_id or None,
                            "pane_title_marker": self.session_info.get("pane_title_marker"),
                            "session_file": self.project_session_file,
                        }
                    },
                }
            )
        except Exception:
            pass

    def _check_session_health(self) -> Tuple[bool, str]:
        return self._check_session_health_impl(probe_terminal=True)

    def _check_session_health_impl(self, probe_terminal: bool) -> Tuple[bool, str]:
        try:
            if not self.pane_id:
                return False, "Session pane id not found"
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

    def ping(self, display: bool = True) -> Tuple[bool, str]:
        healthy, status = self._check_session_health()
        msg = (
            f"CodeBuddy connection OK ({status})" if healthy
            else f"CodeBuddy connection error: {status}"
        )
        if display:
            print(msg)
        return healthy, msg

    def get_status(self) -> Dict[str, Any]:
        healthy, status = self._check_session_health()
        return {
            "session_id": self.session_id,
            "terminal": self.terminal,
            "pane_id": self.pane_id,
            "healthy": healthy,
            "status": status,
        }
