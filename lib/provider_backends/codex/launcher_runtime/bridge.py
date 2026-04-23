from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from provider_backends.codex.runtime_artifacts import codex_runtime_artifact_layout
from provider_profiles import load_resolved_provider_profile

from .command import prepare_codex_home_overrides
from .session_paths import session_file_for_runtime_dir


def post_launch(backend: object, pane_id: str, runtime_dir: Path, launch_session_id: str, prepared_state: dict[str, object]) -> None:
    del launch_session_id
    del prepared_state
    artifacts = codex_runtime_artifact_layout(runtime_dir)
    write_pane_pid(backend, pane_id, artifacts.codex_pid)
    spawn_codex_bridge(runtime_dir=runtime_dir, pane_id=pane_id)
    validate_bridge_bootstrap(runtime_dir)


def spawn_codex_bridge(*, runtime_dir: Path, pane_id: str) -> None:
    artifacts = codex_runtime_artifact_layout(runtime_dir)
    env = os.environ.copy()
    env['CODEX_TERMINAL'] = 'tmux'
    env['CODEX_TMUX_SESSION'] = pane_id
    env['CODEX_RUNTIME_DIR'] = str(runtime_dir)
    env['CODEX_INPUT_FIFO'] = str(artifacts.input_fifo)
    env['CODEX_OUTPUT_FIFO'] = str(artifacts.output_fifo)
    env['CODEX_TMUX_LOG'] = str(artifacts.bridge_log)
    env.update(bridge_runtime_env(runtime_dir))
    existing_pythonpath = env.get('PYTHONPATH', '')
    lib_root = str(Path(__file__).resolve().parents[3])
    env['PYTHONPATH'] = lib_root if not existing_pythonpath else lib_root + os.pathsep + existing_pythonpath
    with artifacts.bridge_stdout_log.open('ab') as stdout_log, artifacts.bridge_stderr_log.open('ab') as stderr_log:
        proc = subprocess.Popen(
            [sys.executable, '-m', 'provider_backends.codex.bridge', '--runtime-dir', str(runtime_dir)],
            env=env,
            stdout=stdout_log,
            stderr=stderr_log,
            start_new_session=True,
        )
    artifacts.bridge_pid.write_text(f'{proc.pid}\n', encoding='utf-8')


def bridge_runtime_env(runtime_dir: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    session_file = session_file_for_runtime_dir(runtime_dir)
    if session_file is not None:
        env['CCB_SESSION_FILE'] = str(session_file)
    profile = load_resolved_provider_profile(runtime_dir)
    env.update(prepare_codex_home_overrides(runtime_dir, profile))
    return env


def validate_bridge_bootstrap(runtime_dir: Path) -> None:
    artifacts = codex_runtime_artifact_layout(runtime_dir)
    missing: list[str] = []
    if not artifacts.input_fifo.exists():
        missing.append(str(artifacts.input_fifo.name))
    if not artifacts.output_fifo.exists():
        missing.append(str(artifacts.output_fifo.name))
    if not artifacts.completion_dir.is_dir():
        missing.append(str(artifacts.completion_dir.name))
    if not artifacts.bridge_log.is_file():
        missing.append(str(artifacts.bridge_log.name))
    if not artifacts.bridge_pid.is_file():
        missing.append(str(artifacts.bridge_pid.name))
    if missing:
        joined = ', '.join(missing)
        raise RuntimeError(f'codex runtime bootstrap missing declared artifacts: {joined}')


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


__all__ = ['bridge_runtime_env', 'post_launch', 'spawn_codex_bridge', 'validate_bridge_bootstrap', 'write_pane_pid']
