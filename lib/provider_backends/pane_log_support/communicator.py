from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from pane_registry_runtime import upsert_registry
from project_id import compute_ccb_project_id
from provider_sessions.files import find_project_session_file
from terminal_runtime import get_backend_for_session, get_pane_id_from_session


class PaneLogCommunicatorBase:
    provider_key = ''
    provider_label = ''
    session_filename = ''
    sync_timeout_env = ''
    missing_session_message = ''
    unhealthy_message = ''
    ping_ok_template = '{provider} connection OK ({status})'
    ping_error_template = '{provider} connection error: {status}'
    reader_cls = None

    def __init__(self, lazy_init: bool = False):
        self.session_info = self._load_session_info()
        if not self.session_info:
            raise RuntimeError(self.missing_session_message)

        self.ccb_session_id = str(self.session_info.get('ccb_session_id') or '').strip()
        self.terminal = self.session_info.get('terminal', 'tmux')
        self.pane_id = get_pane_id_from_session(self.session_info) or ''
        self.pane_title_marker = self.session_info.get('pane_title_marker') or ''
        self.backend = get_backend_for_session(self.session_info)
        self.timeout = int(os.environ.get(self.sync_timeout_env, os.environ.get('CCB_SYNC_TIMEOUT', '3600')))
        self.project_session_file = self.session_info.get('_session_file')

        self._log_reader = None
        self._log_reader_primed = False

        self._publish_registry()

        if not lazy_init:
            self._ensure_log_reader()
            healthy, msg = self._check_session_health()
            if not healthy:
                raise RuntimeError(self.unhealthy_message.format(status=msg))

    @property
    def log_reader(self):
        if self._log_reader is None:
            self._ensure_log_reader()
        assert self._log_reader is not None
        return self._log_reader

    def _ensure_log_reader(self) -> None:
        if self._log_reader is not None:
            return
        work_dir_hint = self.session_info.get('work_dir')
        log_work_dir = Path(work_dir_hint) if isinstance(work_dir_hint, str) and work_dir_hint else None

        pane_log_path: Optional[Path] = None
        raw_log_path = self.session_info.get('pane_log_path')
        if raw_log_path:
            pane_log_path = Path(str(raw_log_path)).expanduser()
        elif self.session_info.get('runtime_dir'):
            pane_log_path = Path(str(self.session_info['runtime_dir'])) / 'pane.log'

        self._log_reader = self.reader_cls(work_dir=log_work_dir, pane_log_path=pane_log_path)
        self._log_reader_primed = True

    def _find_session_file(self) -> Optional[Path]:
        env_session = (os.environ.get('CCB_SESSION_FILE') or '').strip()
        if env_session:
            try:
                session_path = Path(os.path.expanduser(env_session))
                if session_path.name == self.session_filename and session_path.is_file():
                    return session_path
            except Exception:
                pass
        return find_project_session_file(Path.cwd(), self.session_filename)

    def _load_session_info(self) -> Optional[dict]:
        project_session = self._find_session_file()
        if not project_session:
            return None
        try:
            with project_session.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:
            return None
        if not isinstance(data, dict) or data.get('active', False) is False:
            return None
        data['_session_file'] = str(project_session)
        return data

    def _publish_registry(self) -> None:
        try:
            wd = self.session_info.get('work_dir')
            ccb_pid = compute_ccb_project_id(Path(wd)) if isinstance(wd, str) and wd else ''
            upsert_registry(
                {
                    'ccb_session_id': self.ccb_session_id,
                    'ccb_project_id': ccb_pid or None,
                    'work_dir': wd,
                    'terminal': self.terminal,
                    'providers': {
                        self.provider_key: {
                            'pane_id': self.pane_id or None,
                            'pane_title_marker': self.session_info.get('pane_title_marker'),
                            'session_file': self.project_session_file,
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
                return False, 'Session pane id not found'
            if probe_terminal and self.backend:
                pane_alive = self.backend.is_alive(self.pane_id)
                if not pane_alive:
                    return False, f'{self.terminal} session {self.pane_id} not found'
            return True, 'Session OK'
        except Exception as exc:
            return False, f'Check failed: {exc}'

    def ping(self, display: bool = True) -> Tuple[bool, str]:
        healthy, status = self._check_session_health()
        msg = (
            self.ping_ok_template.format(provider=self.provider_label, status=status)
            if healthy
            else self.ping_error_template.format(provider=self.provider_label, status=status)
        )
        if display:
            print(msg)
        return healthy, msg

    def get_status(self) -> Dict[str, Any]:
        healthy, status = self._check_session_health()
        return {
            'ccb_session_id': self.ccb_session_id,
            'terminal': self.terminal,
            'pane_id': self.pane_id,
            'healthy': healthy,
            'status': status,
        }


__all__ = ['PaneLogCommunicatorBase']
