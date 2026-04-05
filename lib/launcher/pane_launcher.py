from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from terminal_runtime import TmuxBackend

from launcher.tmux_helpers import spawn_tmux_pane


@dataclass
class LauncherTmuxPaneLauncher:
    script_dir: Path
    tmux_panes: dict[str, str]
    backend_factory: Callable[[], object] = TmuxBackend
    spawn_tmux_pane_fn: Callable[..., str] = spawn_tmux_pane
    subprocess_run_fn: Callable[..., object] = subprocess.run
    subprocess_popen_fn: Callable[..., object] = subprocess.Popen

    def start_simple_target(
        self,
        *,
        target_key: str,
        runtime: Path,
        cwd: Path,
        start_cmd: str,
        pane_title_marker: str,
        agent_label: str,
        parent_pane: str | None,
        direction: str | None,
        write_session_fn: Callable[..., bool],
    ) -> str:
        runtime.mkdir(parents=True, exist_ok=True)
        backend = self.backend_factory()
        pane_id = self.spawn_tmux_pane_fn(
            backend,
            cwd=cwd,
            cmd=start_cmd,
            title=pane_title_marker,
            agent_label=agent_label,
            existing_panes=self.tmux_panes,
            direction=direction,
            parent_pane=parent_pane,
        )
        self.tmux_panes[target_key] = pane_id
        write_session_fn(
            runtime,
            None,
            pane_id=pane_id,
            pane_title_marker=pane_title_marker,
            start_cmd=start_cmd,
        )
        return pane_id

    def start_codex(
        self,
        *,
        runtime: Path,
        cwd: Path,
        start_cmd: str,
        pane_title_marker: str,
        agent_label: str,
        parent_pane: str | None,
        direction: str | None,
        write_session_fn: Callable[..., bool],
    ) -> str:
        runtime.mkdir(parents=True, exist_ok=True)
        input_fifo = runtime / 'input.fifo'
        output_fifo = runtime / 'output.fifo'
        self._ensure_fifo(input_fifo, 0o600)
        self._ensure_fifo(output_fifo, 0o644)

        backend = self.backend_factory()
        pane_id = self.spawn_tmux_pane_fn(
            backend,
            cwd=cwd,
            cmd=start_cmd,
            title=pane_title_marker,
            agent_label=agent_label,
            existing_panes=self.tmux_panes,
            direction=direction,
            parent_pane=parent_pane,
        )
        self.tmux_panes['codex'] = pane_id

        self._write_tmux_pane_pid(pane_id, runtime / 'codex.pid')
        self._spawn_codex_bridge(runtime=runtime, pane_id=pane_id)

        write_session_fn(
            runtime,
            None,
            input_fifo,
            output_fifo,
            pane_id=pane_id,
            pane_title_marker=pane_title_marker,
            codex_start_cmd=start_cmd,
        )
        return pane_id

    def _ensure_fifo(self, path: Path, mode: int) -> None:
        if path.exists():
            return
        os.mkfifo(path, mode)

    def _write_tmux_pane_pid(self, pane_id: str, target_path: Path) -> None:
        try:
            result = self.subprocess_run_fn(
                ['tmux', 'display-message', '-p', '-t', pane_id, '#{pane_pid}'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True,
            )
        except Exception:
            return
        pane_pid = (getattr(result, 'stdout', '') or '').strip()
        if pane_pid.isdigit():
            target_path.write_text(pane_pid + '\n', encoding='utf-8')

    def _spawn_codex_bridge(self, *, runtime: Path, pane_id: str) -> None:
        bridge_script = self.script_dir / 'lib' / 'provider_backends' / 'codex' / 'bridge.py'
        bridge_env = os.environ.copy()
        bridge_env['CODEX_TERMINAL'] = 'tmux'
        bridge_env['CODEX_TMUX_SESSION'] = pane_id
        bridge_env['CODEX_RUNTIME_DIR'] = str(runtime)
        bridge_env['CODEX_INPUT_FIFO'] = str(runtime / 'input.fifo')
        bridge_env['CODEX_OUTPUT_FIFO'] = str(runtime / 'output.fifo')
        bridge_env['CODEX_TMUX_LOG'] = str(runtime / 'bridge_output.log')
        bridge_env['PYTHONPATH'] = str(self.script_dir) + os.pathsep + bridge_env.get('PYTHONPATH', '')
        bridge_proc = self.subprocess_popen_fn(
            [sys.executable, str(bridge_script), '--runtime-dir', str(runtime)],
            env=bridge_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            (runtime / 'bridge.pid').write_text(str(bridge_proc.pid), encoding='utf-8')
        except Exception:
            pass
