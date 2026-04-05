from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .parsing import extract_assistant_blocks, extract_conversation_pairs, strip_ansi


class PaneLogReaderBase:
    poll_env_var = 'CCB_PANE_LOG_POLL_INTERVAL'

    def __init__(self, work_dir: Optional[Path] = None, pane_log_path: Optional[Path] = None):
        self.work_dir = work_dir or Path.cwd()
        self._pane_log_path: Optional[Path] = pane_log_path
        try:
            poll = float(os.environ.get(self.poll_env_var, '0.05'))
        except Exception:
            poll = 0.05
        self._poll_interval = min(0.5, max(0.02, poll))

    def set_pane_log_path(self, path: Optional[Path]) -> None:
        if path:
            try:
                candidate = path if isinstance(path, Path) else Path(str(path)).expanduser()
            except Exception:
                return
            self._pane_log_path = candidate

    def _resolve_log_path(self) -> Optional[Path]:
        if self._pane_log_path and self._pane_log_path.exists():
            return self._pane_log_path
        return None

    def capture_state(self) -> Dict[str, Any]:
        log_path = self._resolve_log_path()
        offset = 0
        if log_path and log_path.exists():
            try:
                offset = log_path.stat().st_size
            except OSError:
                offset = 0
        return {'pane_log_path': log_path, 'offset': offset}

    def wait_for_message(self, state: Dict[str, Any], timeout: float) -> Tuple[Optional[str], Dict[str, Any]]:
        return self._read_since(state, timeout=timeout, block=True)

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        return self._read_since(state, timeout=0.0, block=False)

    def wait_for_events(self, state: Dict[str, Any], timeout: float) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        return self._read_since_events(state, timeout=timeout, block=True)

    def try_get_events(self, state: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        return self._read_since_events(state, timeout=0.0, block=False)

    def latest_message(self) -> Optional[str]:
        log_path = self._resolve_log_path()
        if not log_path or not log_path.exists():
            return None
        try:
            raw = log_path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            return None
        clean = strip_ansi(raw)
        blocks = extract_assistant_blocks(clean)
        return blocks[-1] if blocks else None

    def latest_conversations(self, n: int = 1) -> List[Tuple[str, str]]:
        log_path = self._resolve_log_path()
        if not log_path or not log_path.exists():
            return []
        try:
            raw = log_path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            return []
        clean = strip_ansi(raw)
        pairs = extract_conversation_pairs(clean)
        return pairs[-max(1, int(n)) :]

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

            if current_state.get('pane_log_path') != log_path:
                current_state['pane_log_path'] = log_path
                current_state['offset'] = 0

            message, current_state = self._read_new_content(log_path, current_state)
            if message:
                return message, current_state

            if not block or time.time() >= deadline:
                return None, current_state
            time.sleep(self._poll_interval)

    def _read_new_content(self, log_path: Path, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        offset = int(state.get('offset') or 0)
        try:
            size = log_path.stat().st_size
        except OSError:
            return None, state

        if size < offset:
            offset = 0
        if size == offset:
            return None, state

        try:
            with log_path.open('rb') as handle:
                handle.seek(offset)
                data = handle.read()
        except OSError:
            return None, state

        new_offset = offset + len(data)
        text = data.decode('utf-8', errors='replace')
        clean = strip_ansi(text)
        blocks = extract_assistant_blocks(clean)
        latest = blocks[-1] if blocks else None

        new_state = {'pane_log_path': log_path, 'offset': new_offset}
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

            if current_state.get('pane_log_path') != log_path:
                current_state['pane_log_path'] = log_path
                current_state['offset'] = 0

            events, current_state = self._read_new_events(log_path, current_state)
            if events:
                return events, current_state

            if not block or time.time() >= deadline:
                return [], current_state
            time.sleep(self._poll_interval)

    def _read_new_events(self, log_path: Path, state: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        offset = int(state.get('offset') or 0)
        try:
            size = log_path.stat().st_size
        except OSError:
            return [], state

        if size < offset:
            offset = 0
        if size == offset:
            return [], state

        try:
            with log_path.open('rb') as handle:
                handle.seek(offset)
                data = handle.read()
        except OSError:
            return [], state

        new_offset = offset + len(data)
        text = data.decode('utf-8', errors='replace')
        clean = strip_ansi(text)

        events: List[Tuple[str, str]] = []
        for user_msg, assistant_msg in extract_conversation_pairs(clean):
            if user_msg:
                events.append(('user', user_msg))
            if assistant_msg:
                events.append(('assistant', assistant_msg))

        new_state = {'pane_log_path': log_path, 'offset': new_offset}
        return events, new_state


__all__ = ['PaneLogReaderBase']
