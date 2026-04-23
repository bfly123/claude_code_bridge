from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from provider_profiles import load_resolved_provider_profile
from runtime_pid_cleanup import assign_process_to_named_job, runtime_job_object_name

from .command import prepare_codex_home_overrides
from .session_paths import session_file_for_runtime_dir, update_runtime_session_payload


def post_launch(backend: object, pane_id: str, runtime_dir: Path, launch_session_id: str, prepared_state: dict[str, object]) -> None:
    del launch_session_id
    runtime_pid = write_pane_pid(backend, pane_id, runtime_dir / 'codex.pid')
    job_owner_pid = spawn_codex_bridge(runtime_dir=runtime_dir, pane_id=pane_id)
    runtime_job_id = str(prepared_state.get('job_id') or '').strip() or None
    windows_job_id = ensure_windows_job_object(runtime_dir=runtime_dir, pids=(runtime_pid, job_owner_pid))
    if windows_job_id:
        runtime_job_id = windows_job_id
    update_runtime_session_payload(
        runtime_dir,
        job_id=runtime_job_id,
        runtime_pid=runtime_pid,
        job_owner_pid=job_owner_pid,
    )


def spawn_codex_bridge(*, runtime_dir: Path, pane_id: str) -> int | None:
    env = os.environ.copy()
    env['CODEX_TERMINAL'] = 'tmux'
    env['CODEX_TMUX_SESSION'] = pane_id
    env['CODEX_RUNTIME_DIR'] = str(runtime_dir)
    env['CODEX_INPUT_FIFO'] = str(runtime_dir / 'input.fifo')
    env['CODEX_OUTPUT_FIFO'] = str(runtime_dir / 'output.fifo')
    env['CODEX_TMUX_LOG'] = str(runtime_dir / 'bridge_output.log')
    env.update(bridge_runtime_env(runtime_dir))
    existing_pythonpath = env.get('PYTHONPATH', '')
    lib_root = str(Path(__file__).resolve().parents[3])
    env['PYTHONPATH'] = lib_root if not existing_pythonpath else lib_root + os.pathsep + existing_pythonpath
    stdout_log = open(runtime_dir / 'bridge.stdout.log', 'ab')
    stderr_log = open(runtime_dir / 'bridge.stderr.log', 'ab')
    proc = subprocess.Popen(
        [sys.executable, '-m', 'provider_backends.codex.bridge', '--runtime-dir', str(runtime_dir)],
        env=env,
        stdout=stdout_log,
        stderr=stderr_log,
        start_new_session=True,
    )
    (runtime_dir / 'bridge.pid').write_text(f'{proc.pid}\n', encoding='utf-8')
    return proc.pid


def ensure_windows_job_object(
    *,
    runtime_dir: Path,
    pids: tuple[int | None, ...],
    os_name: str | None = None,
    assign_process_to_named_job_fn=assign_process_to_named_job,
    job_name_fn=runtime_job_object_name,
) -> str | None:
    if str(os_name or os.name) != 'nt':
        return None
    normalized_pids: list[int] = []
    seen: set[int] = set()
    for pid in pids:
        if pid is None:
            continue
        normalized_pid = int(pid)
        if normalized_pid <= 0 or normalized_pid in seen:
            continue
        seen.add(normalized_pid)
        normalized_pids.append(normalized_pid)
    if not normalized_pids:
        return None
    job_name = str(job_name_fn(runtime_dir) or '').strip()
    if not job_name:
        return None
    return job_name if all(assign_process_to_named_job_fn(job_name, pid) for pid in normalized_pids) else None


def bridge_runtime_env(runtime_dir: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    session_file = session_file_for_runtime_dir(runtime_dir)
    if session_file is not None:
        env['CCB_SESSION_FILE'] = str(session_file)
    profile = load_resolved_provider_profile(runtime_dir)
    env.update(prepare_codex_home_overrides(runtime_dir, profile))
    return env


def write_pane_pid(backend: object, pane_id: str, path: Path) -> int | None:
    try:
        result = backend._tmux_run(  # type: ignore[attr-defined]
            ['display-message', '-p', '-t', pane_id, '#{pane_pid}'],
            capture=True,
            timeout=1.0,
        )
    except Exception:
        return None
    pane_pid = (result.stdout or '').strip()
    if pane_pid.isdigit():
        pid = int(pane_pid)
        path.write_text(f'{pid}\n', encoding='utf-8')
        return pid
    return None


__all__ = ['ensure_windows_job_object', 'post_launch', 'spawn_codex_bridge', 'write_pane_pid']
