"""
Codex dual-window bridge
Sends commands to Codex through tmux-backed sessions.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from provider_core.runtime_specs import provider_marker_prefix
from provider_backends.codex.comm_runtime.binding import extract_session_id
from provider_backends.codex.comm_runtime.log_reader_facade import CodexLogReader
from provider_backends.codex.session import CodexProjectSession
from terminal_runtime import TmuxBackend


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.0, value)


class TerminalCodexSession:
    """Inject commands to Codex CLI via tmux-backed session."""

    def __init__(self, pane_id: str):
        self.pane_id = pane_id
        self.backend = TmuxBackend()

    def send(self, text: str) -> None:
        command = text.replace("\r", " ").replace("\n", " ").strip()
        if command:
            strict_send = getattr(self.backend, "send_text_to_pane", None)
            if callable(strict_send):
                strict_send(self.pane_id, command)
            else:
                self.backend.send_text(self.pane_id, command)


class CodexBindingTracker:
    def __init__(self, runtime_dir: Path):
        self.runtime_dir = runtime_dir
        raw_session_file = str(os.environ.get("CCB_SESSION_FILE") or "").strip()
        self.session_file = Path(raw_session_file).expanduser() if raw_session_file else None
        self._poll_interval = _env_float("CCB_CODEX_BIND_POLL_INTERVAL", 0.5)
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self.session_file is None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="codex-binding-tracker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _loop(self) -> None:
        while self._running:
            try:
                self.refresh_once()
            except Exception:
                pass
            time.sleep(max(0.05, self._poll_interval))

    def refresh_once(self) -> bool:
        if self.session_file is None or not self.session_file.is_file():
            return False
        data = _read_session_data(self.session_file)
        if not isinstance(data, dict):
            return False
        work_dir = _session_work_dir(data)
        if work_dir is None:
            return False
        log_reader = CodexLogReader(
            root=_session_root(data),
            log_path=_path_or_none(data.get("codex_session_path")),
            session_id_filter=str(data.get("codex_session_id") or "").strip() or None,
            work_dir=work_dir,
            follow_workspace_sessions=True,
        )
        log_path = log_reader.current_log_path()
        if log_path is None or not log_path.is_file():
            return False
        session = CodexProjectSession(session_file=self.session_file, data=data)
        before = (
            str(data.get("codex_session_path") or "").strip(),
            str(data.get("codex_session_id") or "").strip(),
            str(data.get("codex_start_cmd") or "").strip(),
            str(data.get("start_cmd") or "").strip(),
        )
        session.update_codex_log_binding(log_path=str(log_path), session_id=extract_session_id(log_path))
        after = (
            str(session.data.get("codex_session_path") or "").strip(),
            str(session.data.get("codex_session_id") or "").strip(),
            str(session.data.get("codex_start_cmd") or "").strip(),
            str(session.data.get("start_cmd") or "").strip(),
        )
        return before != after


class DualBridge:
    """Claude ↔ Codex bridge main process"""

    def __init__(self, runtime_dir: Path):
        self.runtime_dir = runtime_dir
        self.input_fifo = self.runtime_dir / "input.fifo"
        self.history_dir = self.runtime_dir / "history"
        self.history_file = self.history_dir / "session.jsonl"
        self.bridge_log = self.runtime_dir / "bridge.log"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.binding_tracker = CodexBindingTracker(runtime_dir)

        pane_id = os.environ.get("CODEX_TMUX_SESSION")
        if not pane_id:
            raise RuntimeError("Missing CODEX_TMUX_SESSION environment variable")

        self.codex_session = TerminalCodexSession(pane_id)
        self._running = True
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, _: Any) -> None:
        self._running = False
        self.binding_tracker.stop()
        self._log_console(f"⚠️ Received signal {signum}, exiting...")

    def run(self) -> int:
        self._log_console("🔌 Codex bridge started, waiting for Claude commands...")
        self.binding_tracker.start()
        idle_sleep = _env_float("CCB_BRIDGE_IDLE_SLEEP", 0.05)
        error_backoff_min = _env_float("CCB_BRIDGE_ERROR_BACKOFF_MIN", 0.05)
        error_backoff_max = _env_float("CCB_BRIDGE_ERROR_BACKOFF_MAX", 0.2)
        error_backoff = max(0.0, min(error_backoff_min, error_backoff_max))
        try:
            while self._running:
                try:
                    payload = self._read_request()
                    if payload is None:
                        if idle_sleep:
                            time.sleep(idle_sleep)
                        continue
                    self._process_request(payload)
                    error_backoff = max(0.0, min(error_backoff_min, error_backoff_max))
                except KeyboardInterrupt:
                    self._running = False
                except Exception as exc:
                    self._log_console(f"❌ Failed to process message: {exc}")
                    self._log_bridge(f"error: {exc}")
                    if error_backoff:
                        time.sleep(error_backoff)
                    if error_backoff_max:
                        error_backoff = min(error_backoff_max, max(error_backoff_min, error_backoff * 2))
        finally:
            self.binding_tracker.stop()

        self._log_console("👋 Codex bridge exited")
        return 0

    def _read_request(self) -> Optional[Dict[str, Any]]:
        if not self.input_fifo.exists():
            return None
        try:
            with self.input_fifo.open("r", encoding="utf-8") as fifo:
                line = fifo.readline()
                if not line:
                    return None
                return json.loads(line)
        except (OSError, json.JSONDecodeError):
            return None

    def _process_request(self, payload: Dict[str, Any]) -> None:
        content = payload.get("content", "")
        marker = payload.get("marker") or self._generate_marker()

        timestamp = self._timestamp()
        self._log_bridge(json.dumps({"marker": marker, "question": content, "time": timestamp}, ensure_ascii=False))
        self._append_history("claude", content, marker)

        try:
            self.codex_session.send(content)
        except Exception as exc:
            msg = f"❌ Failed to send to Codex: {exc}"
            self._append_history("codex", msg, marker)
            self._log_console(msg)

    def _append_history(self, role: str, content: str, marker: str) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "marker": marker,
            "content": content,
        }
        try:
            with self.history_file.open("a", encoding="utf-8") as handle:
                json.dump(entry, handle, ensure_ascii=False)
                handle.write("\n")
        except Exception as exc:
            self._log_console(f"⚠️ Failed to write history: {exc}")

    def _log_bridge(self, message: str) -> None:
        try:
            with self.bridge_log.open("a", encoding="utf-8") as handle:
                handle.write(f"{self._timestamp()} {message}\n")
        except Exception:
            pass

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _generate_marker() -> str:
        return f"{provider_marker_prefix('codex')}-{int(time.time())}-{os.getpid()}"

    @staticmethod
    def _log_console(message: str) -> None:
        print(message, flush=True)


def _path_or_none(value: object) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser()
    except Exception:
        return None


def _read_session_data(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _session_work_dir(data: dict[str, object]) -> Path | None:
    for key in ("work_dir", "workspace_path", "start_dir"):
        raw = str(data.get(key) or "").strip()
        if not raw:
            continue
        try:
            return Path(raw).expanduser()
        except Exception:
            continue
    return None


def _session_root(data: dict[str, object]) -> Path:
    raw_root = str(data.get("codex_session_root") or os.environ.get("CODEX_SESSION_ROOT") or "").strip()
    if raw_root:
        return Path(raw_root).expanduser()
    raw_home = str(data.get("codex_home") or os.environ.get("CODEX_HOME") or "").strip()
    if raw_home:
        return Path(raw_home).expanduser() / "sessions"
    return Path.home() / ".codex" / "sessions"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claude-Codex bridge")
    parser.add_argument("--runtime-dir", required=True, help="Runtime directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir)
    bridge = DualBridge(runtime_dir)
    return bridge.run()


if __name__ == "__main__":
    raise SystemExit(main())
