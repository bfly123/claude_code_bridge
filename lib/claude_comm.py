"""
Claude communication module.

Reads replies from ~/.claude/projects/<project-key>/<session-id>.jsonl and
sends prompts by injecting text into the Claude pane via the configured backend.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ccb_config import apply_backend_env
from ccb_protocol import is_done_text, make_req_id, strip_done_text
from laskd_protocol import wrap_claude_prompt
from claude_session_resolver import resolve_claude_session
from pane_registry import upsert_registry
from project_id import compute_ccb_project_id
from session_utils import safe_write_session
from terminal import get_backend_for_session, get_pane_id_from_session

apply_backend_env()


CLAUDE_PROJECTS_ROOT = Path(
    os.environ.get("CLAUDE_PROJECTS_ROOT")
    or os.environ.get("CLAUDE_PROJECT_ROOT")
    or (Path.home() / ".claude" / "projects")
).expanduser()


def _project_key_for_path(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _normalize_project_path(value: str | Path) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        path = Path(raw).expanduser()
        try:
            path = path.resolve()
        except Exception:
            path = path.absolute()
        raw = str(path)
    except Exception:
        raw = str(value)
    raw = raw.replace("\\", "/").rstrip("/")
    if os.name == "nt":
        raw = raw.lower()
    return raw


def _candidate_project_paths(work_dir: Path) -> list[str]:
    candidates: list[Path] = []
    env_pwd = os.environ.get("PWD")
    if env_pwd:
        try:
            candidates.append(Path(env_pwd))
        except Exception:
            pass
    candidates.append(work_dir)
    try:
        candidates.append(work_dir.resolve())
    except Exception:
        pass

    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_project_path(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _candidate_project_dirs(root: Path, work_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    env_pwd = os.environ.get("PWD")
    if env_pwd:
        try:
            candidates.append(Path(env_pwd))
        except Exception:
            pass
    candidates.append(work_dir)
    try:
        candidates.append(work_dir.resolve())
    except Exception:
        pass

    out: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _project_key_for_path(candidate)
        if key in seen:
            continue
        seen.add(key)
        out.append(root / key)
    return out


def _extract_content_text(content: Any) -> Optional[str]:
    if content is None:
        return None
    if isinstance(content, str):
        return content.strip() or None
    if not isinstance(content, list):
        return None
    texts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip().lower()
        if item_type in ("thinking", "thinking_delta"):
            continue
        text = item.get("text")
        if not text and item_type == "text":
            text = item.get("content")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    if not texts:
        return None
    return "\n".join(texts).strip()


def _extract_message(entry: dict, role: str) -> Optional[str]:
    if not isinstance(entry, dict):
        return None
    entry_type = (entry.get("type") or "").strip().lower()

    # 1. response_item entries
    if entry_type == "response_item":
        payload = entry.get("payload", {})
        if not isinstance(payload, dict) or payload.get("type") != "message":
            return None
        if (payload.get("role") or "").lower() != role:
            return None
        return _extract_content_text(payload.get("content"))

    # 2. event_msg entries
    if entry_type == "event_msg":
        payload = entry.get("payload", {})
        if not isinstance(payload, dict):
            return None
        payload_type = (payload.get("type") or "").lower()
        if payload_type in ("agent_message", "assistant_message", "assistant"):
            if (payload.get("role") or "").lower() != role:
                return None
            msg = payload.get("message") or payload.get("content") or payload.get("text")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()
        return None

    # 3. default Claude log shape
    message = entry.get("message")
    if isinstance(message, dict):
        msg_role = (message.get("role") or entry_type).strip().lower()
        if msg_role != role:
            return None
        return _extract_content_text(message.get("content"))
    if entry_type != role:
        return None
    return _extract_content_text(entry.get("content"))


class ClaudeLogReader:
    """Reads Claude session logs from ~/.claude/projects/<key>"""

    def __init__(self, root: Path = CLAUDE_PROJECTS_ROOT, work_dir: Optional[Path] = None, *, use_sessions_index: bool = True):
        self.root = Path(root).expanduser()
        self.work_dir = work_dir or Path.cwd()
        self._preferred_session: Optional[Path] = None
        self._use_sessions_index = bool(use_sessions_index)
        try:
            poll = float(os.environ.get("CLAUDE_POLL_INTERVAL", "0.05"))
        except Exception:
            poll = 0.05
        self._poll_interval = min(0.5, max(0.02, poll))

    def _project_dir(self) -> Path:
        candidates = _candidate_project_dirs(self.root, self.work_dir)
        for candidate in candidates:
            if candidate.exists():
                return candidate
        if candidates:
            return candidates[-1]
        return self.root / _project_key_for_path(self.work_dir)

    def _session_is_sidechain(self, session_path: Path) -> Optional[bool]:
        try:
            with session_path.open("r", encoding="utf-8", errors="replace") as handle:
                for _ in range(20):
                    line = handle.readline()
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(entry, dict) and "isSidechain" in entry:
                        return bool(entry.get("isSidechain"))
        except OSError:
            return None
        return None

    def _parse_sessions_index(self) -> Optional[Path]:
        if not self._use_sessions_index:
            return None
        project_dir = self._project_dir()
        index_path = project_dir / "sessions-index.json"
        if not index_path.exists():
            return None
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return None
        entries = payload.get("entries") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            return None
        candidates = set(_candidate_project_paths(self.work_dir))
        best_path: Optional[Path] = None
        best_mtime = -1
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("isSidechain") is True:
                continue
            project_path = entry.get("projectPath")
            if isinstance(project_path, str) and project_path.strip():
                normalized = _normalize_project_path(project_path)
                if candidates and normalized and normalized not in candidates:
                    continue
            elif candidates:
                continue
            full_path = entry.get("fullPath")
            if not isinstance(full_path, str) or not full_path.strip():
                continue
            try:
                session_path = Path(full_path).expanduser()
            except Exception:
                continue
            if not session_path.is_absolute():
                session_path = (project_dir / session_path).expanduser()
            if not session_path.exists():
                continue
            mtime_raw = entry.get("fileMtime")
            mtime = None
            if isinstance(mtime_raw, (int, float)):
                mtime = int(mtime_raw)
            elif isinstance(mtime_raw, str) and mtime_raw.strip().isdigit():
                try:
                    mtime = int(mtime_raw.strip())
                except Exception:
                    mtime = None
            if mtime is None:
                try:
                    mtime = int(session_path.stat().st_mtime * 1000)
                except OSError:
                    mtime = None
            if mtime is None:
                continue
            if mtime > best_mtime:
                best_mtime = mtime
                best_path = session_path
        return best_path

    def _scan_latest_session_any_project(self) -> Optional[Path]:
        if not self.root.exists():
            return None
        try:
            sessions = sorted(
                (p for p in self.root.glob("*/*.jsonl") if p.is_file() and not p.name.startswith(".")),
                key=lambda p: p.stat().st_mtime,
            )
        except OSError:
            return None
        return sessions[-1] if sessions else None

    def _scan_latest_session(self) -> Optional[Path]:
        project_dir = self._project_dir()
        if not project_dir.exists():
            return None
        try:
            sessions = sorted(
                (p for p in project_dir.glob("*.jsonl") if p.is_file() and not p.name.startswith(".")),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return None
        if not sessions:
            return None
        first_unknown: Optional[Path] = None
        first_any = sessions[0]
        for session in sessions:
            sidechain = self._session_is_sidechain(session)
            if sidechain is False:
                return session
            if sidechain is None and first_unknown is None:
                first_unknown = session
        return first_unknown or first_any

    def _latest_session(self) -> Optional[Path]:
        preferred = self._preferred_session
        index_session = self._parse_sessions_index()
        scanned = self._scan_latest_session() if index_session is None else None
        if preferred and preferred.exists():
            if index_session and index_session.exists():
                try:
                    if index_session.stat().st_mtime > preferred.stat().st_mtime:
                        self._preferred_session = index_session
                        return index_session
                except OSError:
                    pass
                return preferred
            if scanned and scanned.exists():
                try:
                    if scanned.stat().st_mtime > preferred.stat().st_mtime:
                        self._preferred_session = scanned
                        return scanned
                except OSError:
                    pass
            return preferred
        if index_session:
            self._preferred_session = index_session
            return index_session
        if scanned:
            self._preferred_session = scanned
            return scanned
        # Strict by default: only scan within this project's directory. Opt-in to any-project scan if needed.
        if os.environ.get("CLAUDE_ALLOW_ANY_PROJECT_SCAN") in ("1", "true", "yes"):
            any_latest = self._scan_latest_session_any_project()
            if any_latest:
                self._preferred_session = any_latest
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

    def capture_state(self) -> Dict[str, Any]:
        session = self._latest_session()
        offset = 0
        if session and session.exists():
            try:
                offset = session.stat().st_size
            except OSError:
                offset = 0
        return {"session_path": session, "offset": offset, "carry": b""}

    def wait_for_message(self, state: Dict[str, Any], timeout: float) -> Tuple[Optional[str], Dict[str, Any]]:
        return self._read_since(state, timeout=timeout, block=True)

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        return self._read_since(state, timeout=0.0, block=False)

    def wait_for_events(self, state: Dict[str, Any], timeout: float) -> Tuple[list[tuple[str, str]], Dict[str, Any]]:
        return self._read_since_events(state, timeout=timeout, block=True)

    def try_get_events(self, state: Dict[str, Any]) -> Tuple[list[tuple[str, str]], Dict[str, Any]]:
        return self._read_since_events(state, timeout=0.0, block=False)

    def latest_message(self) -> Optional[str]:
        session = self._latest_session()
        if not session or not session.exists():
            return None
        last: Optional[str] = None
        try:
            with session.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    msg = _extract_message(entry, "assistant")
                    if msg:
                        last = msg
        except OSError:
            return None
        return last

    def latest_conversations(self, n: int) -> list[tuple[str, str]]:
        session = self._latest_session()
        if not session or not session.exists():
            return []
        pairs: list[tuple[str, str]] = []
        last_user: str | None = None
        try:
            with session.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    user_msg = _extract_message(entry, "user")
                    if user_msg:
                        last_user = user_msg
                        continue
                    assistant_msg = _extract_message(entry, "assistant")
                    if assistant_msg:
                        pairs.append((last_user or "", assistant_msg))
                        last_user = None
        except OSError:
            return []
        return pairs[-max(1, int(n)) :]

    def _read_since(self, state: Dict[str, Any], timeout: float, block: bool) -> Tuple[Optional[str], Dict[str, Any]]:
        deadline = time.time() + max(0.0, float(timeout)) if block else time.time()
        current_state = dict(state or {})

        while True:
            session = self._latest_session()
            if session is None or not session.exists():
                if not block or time.time() >= deadline:
                    return None, current_state
                time.sleep(self._poll_interval)
                continue

            if current_state.get("session_path") != session:
                current_state["session_path"] = session
                current_state["offset"] = 0
                current_state["carry"] = b""

            message, current_state = self._read_new_messages(session, current_state)
            if message:
                return message, current_state

            if not block or time.time() >= deadline:
                return None, current_state
            time.sleep(self._poll_interval)

    def _read_new_messages(self, session: Path, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        offset = int(state.get("offset") or 0)
        carry = state.get("carry") or b""
        try:
            size = session.stat().st_size
        except OSError:
            return None, state

        if size < offset:
            offset = 0
            carry = b""

        try:
            with session.open("rb") as handle:
                handle.seek(offset)
                data = handle.read()
        except OSError:
            return None, state

        new_offset = offset + len(data)
        buf = carry + data
        lines = buf.split(b"\n")
        if buf and not buf.endswith(b"\n"):
            carry = lines.pop()
        else:
            carry = b""

        latest: Optional[str] = None
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line.decode("utf-8", errors="replace"))
            except Exception:
                continue
            msg = _extract_message(entry, "assistant")
            if msg:
                latest = msg

        new_state = {"session_path": session, "offset": new_offset, "carry": carry}
        return latest, new_state

    def _read_since_events(self, state: Dict[str, Any], timeout: float, block: bool) -> Tuple[list[tuple[str, str]], Dict[str, Any]]:
        deadline = time.time() + max(0.0, float(timeout)) if block else time.time()
        current_state = dict(state or {})

        while True:
            session = self._latest_session()
            if session is None or not session.exists():
                if not block or time.time() >= deadline:
                    return [], current_state
                time.sleep(self._poll_interval)
                continue

            if current_state.get("session_path") != session:
                current_state["session_path"] = session
                current_state["offset"] = 0
                current_state["carry"] = b""

            events, current_state = self._read_new_events(session, current_state)
            if events:
                return events, current_state

            if not block or time.time() >= deadline:
                return [], current_state
            time.sleep(self._poll_interval)

    def _read_new_events(self, session: Path, state: Dict[str, Any]) -> Tuple[list[tuple[str, str]], Dict[str, Any]]:
        offset = int(state.get("offset") or 0)
        carry = state.get("carry") or b""
        try:
            size = session.stat().st_size
        except OSError:
            return [], state

        if size < offset:
            offset = 0
            carry = b""

        try:
            with session.open("rb") as handle:
                handle.seek(offset)
                data = handle.read()
        except OSError:
            return [], state

        new_offset = offset + len(data)
        buf = carry + data
        lines = buf.split(b"\n")
        if buf and not buf.endswith(b"\n"):
            carry = lines.pop()
        else:
            carry = b""

        events: list[tuple[str, str]] = []
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line.decode("utf-8", errors="replace"))
            except Exception:
                continue
            user_msg = _extract_message(entry, "user")
            if user_msg:
                events.append(("user", user_msg))
                continue
            assistant_msg = _extract_message(entry, "assistant")
            if assistant_msg:
                events.append(("assistant", assistant_msg))

        new_state = {"session_path": session, "offset": new_offset, "carry": carry}
        return events, new_state


class ClaudeCommunicator:
    """Communicate with Claude via terminal and read replies from session logs."""

    def __init__(self, lazy_init: bool = False):
        self.session_info = self._load_session_info()
        if not self.session_info:
            raise RuntimeError("❌ No active Claude session found. Run 'ccb claude' (or add claude to ccb.config) first")

        self.session_id = str(
            self.session_info.get("claude_session_id") or self.session_info.get("session_id") or ""
        ).strip()
        self.terminal = self.session_info.get("terminal", "tmux")
        self.pane_id = get_pane_id_from_session(self.session_info) or ""
        self.backend = get_backend_for_session(self.session_info)
        self.timeout = int(os.environ.get("CLAUDE_SYNC_TIMEOUT", os.environ.get("CCB_SYNC_TIMEOUT", "3600")))
        self.marker_prefix = "lask"
        self.project_session_file = self.session_info.get("_session_file")

        self._log_reader: Optional[ClaudeLogReader] = None
        self._log_reader_primed = False

        self._publish_registry()

        if not lazy_init:
            self._ensure_log_reader()
            healthy, msg = self._check_session_health()
            if not healthy:
                raise RuntimeError(f"❌ Session unhealthy: {msg}\nHint: run ccb claude (or add claude to ccb.config) to start a new session")

    @property
    def log_reader(self) -> ClaudeLogReader:
        if self._log_reader is None:
            self._ensure_log_reader()
        return self._log_reader

    def _ensure_log_reader(self) -> None:
        if self._log_reader is not None:
            return
        work_dir_hint = self.session_info.get("work_dir")
        log_work_dir = Path(work_dir_hint) if isinstance(work_dir_hint, str) and work_dir_hint else None
        self._log_reader = ClaudeLogReader(work_dir=log_work_dir)
        preferred_session = self.session_info.get("claude_session_path")
        if preferred_session:
            self._log_reader.set_preferred_session(Path(str(preferred_session)))
        if not self._log_reader_primed:
            self._prime_log_binding()
            self._log_reader_primed = True

    def _load_session_info(self) -> Optional[dict]:
        work_dir = Path.cwd()
        resolution = resolve_claude_session(work_dir)
        if not resolution:
            return None
        data = dict(resolution.data or {})
        if not data:
            return None
        if data.get("active") is False:
            return None
        session_file = resolution.session_file
        if session_file:
            data["_session_file"] = str(session_file)
        data["work_dir"] = str(Path(data.get("work_dir") or work_dir))
        return data

    def _prime_log_binding(self) -> None:
        session_path = self.log_reader.current_session_path()
        if not session_path:
            return
        self._remember_claude_session(session_path)

    def _check_session_health(self) -> Tuple[bool, str]:
        return self._check_session_health_impl(probe_terminal=True)

    def _check_session_health_impl(self, probe_terminal: bool) -> Tuple[bool, str]:
        try:
            if not self.pane_id:
                return False, "Session pane id not found"
            if probe_terminal and self.backend and not self.backend.is_alive(self.pane_id):
                return False, f"{self.terminal} session {self.pane_id} not found"
            return True, "Session OK"
        except Exception as exc:
            return False, f"Check failed: {exc}"

    def _send_via_terminal(self, content: str) -> bool:
        if not self.backend or not self.pane_id:
            raise RuntimeError("Terminal session not configured")
        self.backend.send_text(self.pane_id, content)
        return True

    def _remember_claude_session(self, session_path: Path) -> None:
        if not self.project_session_file:
            return
        if not session_path or not isinstance(session_path, Path):
            return
        try:
            path = Path(self.project_session_file)
            data = {}
            try:
                with path.open("r", encoding="utf-8-sig", errors="replace") as f:
                    data = json.load(f)
            except Exception:
                data = {}
            if not isinstance(data, dict):
                data = {}
            data["claude_session_path"] = str(session_path)
            if session_path.stem and data.get("claude_session_id") != session_path.stem:
                data["claude_session_id"] = session_path.stem
            data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            data["active"] = True
            payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            safe_write_session(path, payload)
            self.session_info["claude_session_path"] = str(session_path)
            if session_path.stem and self.session_info.get("claude_session_id") != session_path.stem:
                self.session_info["claude_session_id"] = session_path.stem
        except Exception:
            return
        self._publish_registry()

    def _publish_registry(self) -> None:
        try:
            ccb_session_id = (self.session_info.get("ccb_session_id") or os.environ.get("CCB_SESSION_ID") or "").strip()
            if not ccb_session_id:
                return
            wd = self.session_info.get("work_dir")
            work_dir = Path(wd) if isinstance(wd, str) and wd else Path.cwd()
            ccb_pid = compute_ccb_project_id(work_dir)
            upsert_registry(
                {
                    "ccb_session_id": ccb_session_id,
                    "ccb_project_id": ccb_pid or None,
                    "work_dir": str(work_dir),
                    "terminal": self.terminal,
                    "providers": {
                        "claude": {
                            "pane_id": self.pane_id or None,
                            "pane_title_marker": self.session_info.get("pane_title_marker"),
                            "session_file": self.project_session_file,
                            "claude_session_id": self.session_info.get("claude_session_id"),
                            "claude_session_path": self.session_info.get("claude_session_path"),
                        }
                    },
                }
            )
        except Exception:
            pass

    def ask_async(self, question: str) -> bool:
        try:
            healthy, status = self._check_session_health_impl(probe_terminal=False)
            if not healthy:
                raise RuntimeError(f"❌ Session error: {status}")
            self._send_via_terminal(question)
            print("✅ Sent to Claude")
            print("Hint: Use lpend to view reply")
            return True
        except Exception as exc:
            print(f"❌ Send failed: {exc}")
            return False

    def ask_sync(self, question: str, timeout: Optional[int] = None) -> Optional[str]:
        try:
            healthy, status = self._check_session_health_impl(probe_terminal=False)
            if not healthy:
                raise RuntimeError(f"❌ Session error: {status}")

            req_id = make_req_id()
            prompt = wrap_claude_prompt(question, req_id)
            state = self.log_reader.capture_state()
            self._send_via_terminal(prompt)

            wait_timeout = self.timeout if timeout is None else int(timeout)
            deadline = None if wait_timeout < 0 else (time.time() + wait_timeout)
            latest = ""
            done_seen = False

            while True:
                if deadline is not None:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        break
                    wait_step = min(remaining, 1.0)
                else:
                    wait_step = 1.0

                reply, state = self.log_reader.wait_for_message(state, timeout=wait_step)
                if reply is None:
                    continue
                latest = str(reply)
                if is_done_text(latest, req_id):
                    done_seen = True
                    break

            if done_seen:
                session_path = self.log_reader.current_session_path()
                if session_path:
                    self._remember_claude_session(session_path)
                return strip_done_text(latest, req_id)
            return strip_done_text(latest, req_id) if latest else None
        except Exception as exc:
            print(f"❌ Send failed: {exc}")
            return None

    def ping(self, display: bool = True) -> Tuple[bool, str]:
        healthy, msg = self._check_session_health_impl(probe_terminal=True)
        if display:
            print(msg)
        return healthy, msg
