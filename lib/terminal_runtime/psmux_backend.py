from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

from .tmux_backend import TmuxBackend


class PsmuxBackend(TmuxBackend):
    def __init__(self, *, socket_name: str | None = None, socket_path: str | None = None):
        super().__init__(socket_name=socket_name, socket_path=socket_path)
        if self._socket_name is None and self._socket_path:
            self._socket_name = _psmux_server_name_from_path(self._socket_path)

    @property
    def backend_impl(self) -> str:
        return 'psmux'

    @property
    def backend_ref(self) -> str | None:
        return str(self._socket_name or '').strip() or None

    def _tmux_base(self) -> list[str]:
        executable = str(os.environ.get('CCB_PSMUX_BIN') or 'psmux').strip() or 'psmux'
        command = [executable]
        if self._socket_name:
            command.extend(['-L', self._socket_name])
        return command

    def respawn_pane(
        self,
        pane_id: str,
        *,
        cmd: str,
        cwd: str | None = None,
        stderr_log_path: str | None = None,
        remain_on_exit: bool = True,
    ) -> None:
        if os.name != 'nt':
            return super().respawn_pane(
                pane_id,
                cmd=cmd,
                cwd=cwd,
                stderr_log_path=stderr_log_path,
                remain_on_exit=remain_on_exit,
            )
        pane_text = str(pane_id or '').strip()
        if not pane_text:
            raise ValueError('pane_id is required')
        cmd_body = str(cmd or '').strip()
        if not cmd_body:
            raise ValueError('cmd is required')
        try:
            self.ensure_pane_log(pane_text)
        except Exception:
            pass
        if stderr_log_path:
            log_path = str(Path(stderr_log_path).expanduser().resolve())
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            cmd_body = f'{cmd_body} 2>> {subprocess.list2cmdline([log_path])}'
        full_command = subprocess.list2cmdline([_windows_cmd_exe(), '/d', '/s', '/c', cmd_body])
        if remain_on_exit:
            self._tmux_run(['set-option', '-p', '-t', pane_text, 'remain-on-exit', 'on'], check=False)
        args = ['respawn-pane', '-k', '-t', pane_text]
        start_dir = str(cwd or '').strip()
        if start_dir and start_dir != '.':
            args.extend(['-c', start_dir])
        args.append(full_command)
        self._tmux_run(args, check=True)
        if remain_on_exit:
            self._tmux_run(['set-option', '-p', '-t', pane_text, 'remain-on-exit', 'on'], check=False)

    def kill_session(self, session_name: str) -> bool:
        if self._socket_name:
            try:
                self._tmux_run(['kill-server'], check=False)
                return True
            except Exception:
                return False
        return super().kill_session(session_name)


def _psmux_server_name_from_path(socket_path: str) -> str:
    raw = str(socket_path or '').strip()
    if not raw:
        return 'default'
    stem = Path(raw).name or 'ccb'
    safe_stem = ''.join(ch if ch.isalnum() or ch in {'-', '_', '.'} else '-' for ch in stem).strip('-.') or 'ccb'
    digest = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]
    return f'{safe_stem}-{digest}'


def _windows_cmd_exe() -> str:
    return os.environ.get('COMSPEC', os.path.join(os.environ.get('SystemRoot', r'C:\WINDOWS'), 'System32', 'cmd.exe'))


__all__ = ['PsmuxBackend']
