#!/usr/bin/env python3
"""
OpenCode communication module

Reads replies from OpenCode storage (~/.local/share/opencode/storage) and sends messages by
injecting text into the OpenCode TUI pane via the configured terminal backend.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ccb_config import apply_backend_env, get_bool_env
from i18n import t
from terminal import get_backend_for_session, get_pane_id_from_session
from fs_watch import FileChangeWaiter
from mailbox import (
    build_mailbox_prompt,
    looks_like_cannot_read_file,
    mailbox_enabled,
    mailbox_threshold,
    write_mailbox_instruction,
)

apply_backend_env()


def _normalize_path_for_match(value: str) -> str:
    try:
        path = Path(value).expanduser()
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


def _default_opencode_storage_root() -> Path:
    env = (os.environ.get("OPENCODE_STORAGE_ROOT") or "").strip()
    if env:
        return Path(env).expanduser()

    # Common defaults
    candidates: list[Path] = []
    candidates.append(Path.home() / ".local" / "share" / "opencode" / "storage")

    # Windows native (best-effort; OpenCode might not use this, but allow it if present)
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        candidates.append(Path(localappdata) / "opencode" / "storage")
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "opencode" / "storage")

    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except Exception:
            continue

    # Fallback to Linux default even if it doesn't exist yet (ping/health will report).
    return candidates[0]


OPENCODE_STORAGE_ROOT = _default_opencode_storage_root()


class OpenCodeLogReader:
    """
    Reads OpenCode session/message/part JSON files.

    Observed storage layout:
      storage/session/<projectID>/ses_*.json
      storage/message/<sessionID>/msg_*.json
      storage/part/<messageID>/prt_*.json
    """

    def __init__(self, root: Path = OPENCODE_STORAGE_ROOT, work_dir: Optional[Path] = None, project_id: str = "global"):
        self.root = Path(root).expanduser()
        self.work_dir = work_dir or Path.cwd()
        self.project_id = (os.environ.get("OPENCODE_PROJECT_ID") or project_id or "global").strip() or "global"

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
        self._change_waiter = FileChangeWaiter(
            [],
            enabled=get_bool_env("CCB_INOTIFY", False),
            poll_interval=self._poll_interval,
            debug_name="opencode",
        )

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

    def _get_latest_session(self) -> Optional[dict]:
        sessions_dir = self._session_dir()
        if not sessions_dir.exists():
            return None

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
                if _path_is_same_or_parent(session_dir_norm, cwd) or _path_is_same_or_parent(cwd, session_dir_norm):
                    matched = True
                    break
            if not matched:
                continue

            if updated > best_updated or (updated == best_updated and mtime >= best_mtime):
                best_match = {"path": path, "payload": payload}
                best_updated = updated
                best_mtime = mtime

        return best_match or best_any

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
    def _extract_text(parts: List[dict]) -> str:
        out: list[str] = []
        for part in parts:
            if part.get("type") != "text":
                continue
            text = part.get("text")
            if isinstance(text, str) and text:
                out.append(text)
        return "".join(out).strip()

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
            return None

        # Detect change via count or last id or completion timestamp.
        if len(assistants) <= prev_count and latest_id == prev_last and completed_i == prev_completed:
            return None

        parts = self._read_parts(str(latest_id))
        return self._extract_text(parts) or None

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
                remaining = max(0.0, deadline - time.time())
                self._change_waiter.update_paths([self._session_dir()])
                self._change_waiter.wait(min(self._poll_interval, remaining) if remaining else self._poll_interval)
                if time.time() >= deadline:
                    return None, state
                continue

            payload = session_entry.get("payload") or {}
            current_session_id = payload.get("id") if isinstance(payload.get("id"), str) else None
            if session_id and current_session_id and current_session_id != session_id:
                # User may have switched sessions; keep following the state-bound session if possible.
                # If that session is no longer the latest, we still try to read it (best-effort) by sticking to session_id.
                current_session_id = session_id
            elif not session_id:
                session_id = current_session_id

            if not current_session_id:
                if not block:
                    return None, state
                remaining = max(0.0, deadline - time.time())
                watch_paths = [self._session_dir()]
                path = session_entry.get("path")
                if isinstance(path, Path):
                    watch_paths.append(path)
                self._change_waiter.update_paths(watch_paths)
                self._change_waiter.wait(min(self._poll_interval, remaining) if remaining else self._poll_interval)
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
                    self._change_waiter.reset_backoff()
                    return reply, new_state

                # Update state baseline even if reply isn't ready yet.
                state = dict(state)
                state["session_updated"] = updated_i

            if not block:
                return None, state

            remaining = max(0.0, deadline - time.time())
            if remaining <= 0:
                return None, state
            watch_paths = [self._session_dir()]
            path = session_entry.get("path")
            if isinstance(path, Path):
                watch_paths.append(path)
            self._change_waiter.update_paths(watch_paths)
            next_forced_due = max(0.0, self._force_read_interval - (time.time() - last_forced_read))
            wait_for = min(remaining, max(0.01, next_forced_due))
            woke = self._change_waiter.wait(wait_for)
            if woke and self._change_waiter.overflowed:
                last_forced_read = 0.0
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


class OpenCodeCommunicator:
    def __init__(self, lazy_init: bool = False):
        self.session_info = self._load_session_info()
        if not self.session_info:
            raise RuntimeError("❌ No active OpenCode session found. Run 'ccb up opencode' first")

        self.session_id = self.session_info["session_id"]
        self.runtime_dir = Path(self.session_info["runtime_dir"])
        self.terminal = self.session_info.get("terminal", os.environ.get("OPENCODE_TERMINAL", "tmux"))
        self.pane_id = get_pane_id_from_session(self.session_info) or ""
        self.backend = get_backend_for_session(self.session_info)

        self.timeout = int(os.environ.get("OPENCODE_SYNC_TIMEOUT", "30"))
        self.marker_prefix = "oask"
        self.project_session_file = self.session_info.get("_session_file")

        self.log_reader = OpenCodeLogReader()

        if not lazy_init:
            healthy, msg = self._check_session_health()
            if not healthy:
                raise RuntimeError(f"❌ Session unhealthy: {msg}\nTip: Run 'ccb up opencode' to start a new session")

    def _load_session_info(self) -> Optional[dict]:
        if "OPENCODE_SESSION_ID" in os.environ:
            terminal = os.environ.get("OPENCODE_TERMINAL", "tmux")
            if terminal == "wezterm":
                pane_id = os.environ.get("OPENCODE_WEZTERM_PANE", "")
            elif terminal == "iterm2":
                pane_id = os.environ.get("OPENCODE_ITERM2_PANE", "")
            else:
                pane_id = ""
            return {
                "session_id": os.environ["OPENCODE_SESSION_ID"],
                "runtime_dir": os.environ["OPENCODE_RUNTIME_DIR"],
                "terminal": terminal,
                "tmux_session": os.environ.get("OPENCODE_TMUX_SESSION", ""),
                "pane_id": pane_id,
                "_session_file": None,
            }

        project_session = Path.cwd() / ".opencode-session"
        if not project_session.exists():
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

    def _send_via_file(self, content: str) -> Optional[Path]:
        try:
            path = write_mailbox_instruction(content)
            prompt = build_mailbox_prompt(path)
            self._send_via_terminal(prompt)
            return path
        except Exception:
            return None

    def _send_message(self, content: str) -> Tuple[str, Dict[str, Any]]:
        marker = self._generate_marker()
        state = self.log_reader.capture_state()
        self._send_via_terminal(content)
        return marker, state

    def _generate_marker(self) -> str:
        return f"{self.marker_prefix}-{int(time.time())}-{os.getpid()}"

    def _remember_opencode_session(self) -> None:
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

        updated = False

        # Save last_work_dir
        last_work_dir = self.session_info.get("last_work_dir")
        if last_work_dir and data.get("last_work_dir") != last_work_dir:
            data["last_work_dir"] = last_work_dir
            updated = True

        if not updated:
            return

        tmp_file = project_file.with_suffix(".tmp")
        try:
            with tmp_file.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_file, project_file)
        except PermissionError as e:
            print(f"⚠️  Cannot update {project_file.name}: {e}", file=sys.stderr)
            print(f"💡 Try: sudo chown $USER:$USER {project_file}", file=sys.stderr)
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️  Failed to update {project_file.name}: {e}", file=sys.stderr)
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass

    def _handle_auto_cwd(self, content: str) -> str:
        """Auto-sync CWD if enabled and changed"""
        if os.environ.get("CCB_AUTO_CWD_SYNC") != "1":
            return content

        try:
            current_cwd = str(Path.cwd().resolve())
        except Exception:
            return content

        last_cwd = self.session_info.get("last_work_dir")
        if last_cwd == current_cwd:
            return content

        if not current_cwd or not os.path.exists(current_cwd):
            if OpenCodeLogReader._debug_enabled():
                print(f"⚠️ Auto-CWD: Skipping invalid CWD: {current_cwd}", file=sys.stderr)
            return content

        print(f"🔄 Auto-sync CWD: {current_cwd}")

        self.session_info["last_work_dir"] = current_cwd
        self._remember_opencode_session()

        return f"cd {current_cwd}\n{content}"

    def ask_async(self, question: str) -> bool:
        try:
            healthy, status = self._check_session_health_impl(probe_terminal=False)
            if not healthy:
                raise RuntimeError(f"❌ Session error: {status}")
            
            question = self._handle_auto_cwd(question)
            if mailbox_enabled() and len(question) > mailbox_threshold():
                if self._send_via_file(question) is None:
                    self._send_via_terminal(question)
            else:
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
            question = self._handle_auto_cwd(question)
            mailbox_path: Optional[Path] = None
            used_mailbox = mailbox_enabled() and len(question) > mailbox_threshold()
            if used_mailbox:
                state = self.log_reader.capture_state()
                mailbox_path = self._send_via_file(question)
                if mailbox_path is None:
                    used_mailbox = False
                    _, state = self._send_message(question)
            else:
                _, state = self._send_message(question)
            wait_timeout = self.timeout if timeout is None else int(timeout)
            print(f"⏳ Waiting for OpenCode reply (timeout {wait_timeout}s)...")
            start_time = time.time()
            message, _ = self.log_reader.wait_for_message(state, float(wait_timeout))
            if message:
                if used_mailbox and looks_like_cannot_read_file(message):
                    if mailbox_path:
                        try:
                            mailbox_path.unlink()
                        except Exception:
                            pass
                    elapsed = time.time() - start_time
                    remaining = max(0.0, float(wait_timeout) - elapsed)
                    _, state = self._send_message(question)
                    message, _ = self.log_reader.wait_for_message(state, remaining)
                    if message:
                        print(f"🤖 {t('reply_from', provider='OpenCode')}")
                        print(message)
                        return message
                    print(f"⏰ {t('timeout_no_reply', provider='OpenCode')}")
                    if self.backend and self.pane_id:
                        try:
                            snapshot = self.backend.capture_pane(self.pane_id, lines=15)
                            if snapshot:
                                print("\n[Last 15 lines of backend terminal]")
                                print(snapshot)
                                print("-" * 40)
                        except Exception:
                            pass
                    return None
                print(f"🤖 {t('reply_from', provider='OpenCode')}")
                print(message)
                if used_mailbox and mailbox_path:
                    try:
                        mailbox_path.unlink()
                    except Exception:
                        pass
                return message
            print(f"⏰ {t('timeout_no_reply', provider='OpenCode')}")
            if self.backend and self.pane_id:
                try:
                    snapshot = self.backend.capture_pane(self.pane_id, lines=15)
                    if snapshot:
                        print("\n[Last 15 lines of backend terminal]")
                        print(snapshot)
                        print("-" * 40)
                except Exception:
                    pass
            return None
        except Exception as exc:
            print(f"❌ Sync ask failed: {exc}")
            return None
