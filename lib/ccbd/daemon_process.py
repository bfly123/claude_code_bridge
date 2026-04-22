from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import time

from ccbd.socket_client import CcbdClient, CcbdClientError


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
    process = subprocess.Popen(
        [sys.executable, str(script), '--project', str(project_root)],
        cwd=str(project_root),
        env=env,
        stdout=stdout_log,
        stderr=stderr_log,
        start_new_session=True,
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
        if process.poll() is not None:
            try:
                CcbdClient(socket_path, timeout_s=probe_timeout_s, ipc_kind=ipc_kind).ping('ccbd')
                return
            except CcbdClientError as exc:
                last_error = str(exc)
            raise CcbdProcessError(f'ccbd exited before ready with code {process.returncode}')
        time.sleep(0.05)
    raise CcbdProcessError(last_error or 'timed out waiting for ccbd to become ready')


def _ccbd_env(*, keeper_pid: int | None) -> dict[str, str]:
    env = dict(os.environ)
    env['PYTHONUNBUFFERED'] = '1'
    lib_root = str(Path(__file__).resolve().parents[1])
    current_pythonpath = env.get('PYTHONPATH')
    env['PYTHONPATH'] = lib_root if not current_pythonpath else lib_root + os.pathsep + current_pythonpath
    if keeper_pid is not None and keeper_pid > 0:
        env['CCB_KEEPER_PID'] = str(int(keeper_pid))
    return env


__all__ = ['CcbdProcessError', 'spawn_ccbd_process']
