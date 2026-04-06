from __future__ import annotations

import json
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from provider_core.runtime_specs import provider_marker_prefix

from .binding import CodexBindingTracker
from .env import env_float
from .session import TerminalCodexSession


class DualBridge:
    """Claude ↔ Codex bridge main process"""

    def __init__(self, runtime_dir: Path):
        self.runtime_dir = runtime_dir
        self.input_fifo = self.runtime_dir / 'input.fifo'
        self.history_dir = self.runtime_dir / 'history'
        self.history_file = self.history_dir / 'session.jsonl'
        self.bridge_log = self.runtime_dir / 'bridge.log'
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.binding_tracker = CodexBindingTracker(runtime_dir)

        pane_id = os.environ.get('CODEX_TMUX_SESSION')
        if not pane_id:
            raise RuntimeError('Missing CODEX_TMUX_SESSION environment variable')

        self.codex_session = TerminalCodexSession(pane_id)
        self._running = True
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, _: Any) -> None:
        self._running = False
        self.binding_tracker.stop()
        self._log_console(f'⚠️ Received signal {signum}, exiting...')

    def run(self) -> int:
        self._log_console('🔌 Codex bridge started, waiting for Claude commands...')
        self.binding_tracker.start()
        idle_sleep = env_float('CCB_BRIDGE_IDLE_SLEEP', 0.05)
        error_backoff_min = env_float('CCB_BRIDGE_ERROR_BACKOFF_MIN', 0.05)
        error_backoff_max = env_float('CCB_BRIDGE_ERROR_BACKOFF_MAX', 0.2)
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
                    self._log_console(f'❌ Failed to process message: {exc}')
                    self._log_bridge(f'error: {exc}')
                    if error_backoff:
                        time.sleep(error_backoff)
                    if error_backoff_max:
                        error_backoff = min(error_backoff_max, max(error_backoff_min, error_backoff * 2))
        finally:
            self.binding_tracker.stop()

        self._log_console('👋 Codex bridge exited')
        return 0

    def _read_request(self) -> Optional[Dict[str, Any]]:
        if not self.input_fifo.exists():
            return None
        try:
            with self.input_fifo.open('r', encoding='utf-8') as fifo:
                line = fifo.readline()
                if not line:
                    return None
                return json.loads(line)
        except (OSError, json.JSONDecodeError):
            return None

    def _process_request(self, payload: Dict[str, Any]) -> None:
        content = payload.get('content', '')
        marker = payload.get('marker') or self._generate_marker()

        timestamp = self._timestamp()
        self._log_bridge(json.dumps({'marker': marker, 'question': content, 'time': timestamp}, ensure_ascii=False))
        self._append_history('claude', content, marker)

        try:
            self.codex_session.send(content)
        except Exception as exc:
            msg = f'❌ Failed to send to Codex: {exc}'
            self._append_history('codex', msg, marker)
            self._log_console(msg)

    def _append_history(self, role: str, content: str, marker: str) -> None:
        entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'role': role,
            'marker': marker,
            'content': content,
        }
        try:
            with self.history_file.open('a', encoding='utf-8') as handle:
                json.dump(entry, handle, ensure_ascii=False)
                handle.write('\n')
        except Exception as exc:
            self._log_console(f'⚠️ Failed to write history: {exc}')

    def _log_bridge(self, message: str) -> None:
        try:
            with self.bridge_log.open('a', encoding='utf-8') as handle:
                handle.write(f'{self._timestamp()} {message}\n')
        except Exception:
            pass

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def _generate_marker() -> str:
        return f"{provider_marker_prefix('codex')}-{int(time.time())}-{os.getpid()}"

    @staticmethod
    def _log_console(message: str) -> None:
        print(message, flush=True)


__all__ = ['DualBridge']
