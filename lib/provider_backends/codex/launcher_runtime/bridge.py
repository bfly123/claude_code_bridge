from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from provider_profiles import load_resolved_provider_profile

from .command import prepare_codex_home_overrides
from .session_paths import session_file_for_runtime_dir


def post_launch(backend: object, pane_id: str, runtime_dir: Path, launch_session_id: str, prepared_state: dict[str, object]) -> None:
    del launch_session_id
    del prepared_state
    write_pane_pid(backend, pane_id, runtime_dir / 'codex.pid')
    spawn_codex_bridge(runtime_dir=runtime_dir, pane_id=pane_id)


def spawn_codex_bridge(*, runtime_dir: Path, pane_id: str) -> None:
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


def bridge_runtime_env(runtime_dir: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    session_file = session_file_for_runtime_dir(runtime_dir)
    if session_file is not None:
        env['CCB_SESSION_FILE'] = str(session_file)
    profile = load_resolved_provider_profile(runtime_dir)
    env.update(prepare_codex_home_overrides(runtime_dir, profile))
    return env


def write_pane_pid(backend: object, pane_id: str, path: Path) -> None:
    try:
        result = backend._tmux_run(  # type: ignore[attr-defined]
            ['display-message', '-p', '-t', pane_id, '#{pane_pid}'],
            capture=True,
            timeout=1.0,
        )
    except Exception:
        return
    pane_pid = (result.stdout or '').strip()
    if pane_pid.isdigit():
        path.write_text(f'{pane_pid}\n', encoding='utf-8')


__all__ = ['post_launch', 'spawn_codex_bridge', 'write_pane_pid']
