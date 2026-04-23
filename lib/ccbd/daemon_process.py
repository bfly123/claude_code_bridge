from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import sys
import time

from ccbd.socket_client import CcbdClient, CcbdClientError
from ccbd.system import ipc_endpoint_connectable


class CcbdProcessError(RuntimeError):
    pass


def _ready_probe_timeout_s(ipc_kind: str | None) -> float:
    return 1.0 if str(ipc_kind or '').strip().lower() == 'named_pipe' else 0.2


def spawn_ccbd_process(
    *,
    project_root: Path,
    socket_path,
    ipc_kind: str | None,
    ccbd_dir: Path,
    timeout_s: float,
    keeper_pid: int | None = None,
) -> None:
    script = Path(__file__).resolve().parent / 'main.py'
    env = _ccbd_env(keeper_pid=keeper_pid)
    ccbd_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = open(ccbd_dir / 'ccbd.stdout.log', 'ab')
    stderr_log = open(ccbd_dir / 'ccbd.stderr.log', 'ab')
    popen_kwargs = {
        'cwd': str(project_root),
        'env': env,
        'stdout': stdout_log,
        'stderr': stderr_log,
    }
    if os.name == 'nt':
        popen_kwargs['creationflags'] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )
    else:
        popen_kwargs['start_new_session'] = True
    process = subprocess.Popen(
        [sys.executable, str(script), '--project', str(project_root)],
        **popen_kwargs,
    )
    _wait_for_ccbd_ready(process=process, socket_path=socket_path, ipc_kind=ipc_kind, timeout_s=timeout_s)


def _wait_for_ccbd_ready(*, process: subprocess.Popen[bytes], socket_path, ipc_kind: str | None, timeout_s: float) -> None:
    deadline = time.time() + max(0.0, float(timeout_s))
    last_error: str | None = None
    probe_timeout_s = _ready_probe_timeout_s(ipc_kind)
    while time.time() < deadline:
        try:
            CcbdClient(socket_path, timeout_s=probe_timeout_s, ipc_kind=ipc_kind).ping('ccbd')
            return
        except CcbdClientError as exc:
            last_error = str(exc)
            if _ready_fallback_allowed(ipc_kind) and _endpoint_ready(socket_path, ipc_kind=ipc_kind, timeout_s=probe_timeout_s):
                return
        if process.poll() is not None:
            try:
                CcbdClient(socket_path, timeout_s=probe_timeout_s, ipc_kind=ipc_kind).ping('ccbd')
                return
            except CcbdClientError as exc:
                last_error = str(exc)
                if _ready_fallback_allowed(ipc_kind) and _endpoint_ready(socket_path, ipc_kind=ipc_kind, timeout_s=probe_timeout_s):
                    return
            raise CcbdProcessError(f'ccbd exited before ready with code {process.returncode}')
        time.sleep(0.05)
    raise CcbdProcessError(last_error or 'timed out waiting for ccbd to become ready')


def _endpoint_ready(socket_path, *, ipc_kind: str | None, timeout_s: float) -> bool:
    try:
        return bool(ipc_endpoint_connectable(socket_path, ipc_kind=ipc_kind, timeout_s=timeout_s))
    except TypeError:
        return bool(ipc_endpoint_connectable(socket_path, timeout_s=timeout_s))


def _ready_fallback_allowed(ipc_kind: str | None) -> bool:
    return str(ipc_kind or '').strip().lower() == 'named_pipe'


def _ccbd_env(*, keeper_pid: int | None) -> dict[str, str]:
    env = dict(os.environ)
    env['PYTHONUNBUFFERED'] = '1'
    env['PATH'] = os.environ.get('PATH', '')
    lib_root = str(Path(__file__).resolve().parents[1])
    current_pythonpath = env.get('PYTHONPATH')
    env['PYTHONPATH'] = lib_root if not current_pythonpath else lib_root + os.pathsep + current_pythonpath
    if os.name == 'nt':
        native_enabled = str(env.get('CCB_EXPERIMENTAL_WINDOWS_NATIVE') or '').strip().lower() in {
            '1', 'true', 'yes', 'on'
        }
        if native_enabled:
            resolved_psmux = str(env.get('CCB_PSMUX_BIN') or '').strip()
            if not resolved_psmux:
                resolved_psmux = shutil.which('psmux') or ''
            if resolved_psmux:
                env['CCB_PSMUX_BIN'] = resolved_psmux
            else:
                raise RuntimeError('psmux not found in PATH; set CCB_PSMUX_BIN')
        if not str(env.get('CCB_WINDOWS_SHELL_BIN') or '').strip():
            resolved_shell = (
                shutil.which('pwsh')
                or shutil.which('powershell')
                or str(Path(r'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe'))
            )
            env['CCB_WINDOWS_SHELL_BIN'] = resolved_shell
    if keeper_pid is not None and keeper_pid > 0:
        env['CCB_KEEPER_PID'] = str(int(keeper_pid))
    return env


__all__ = ['CcbdProcessError', 'spawn_ccbd_process']
