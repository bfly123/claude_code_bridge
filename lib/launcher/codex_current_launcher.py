from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TextIO


@dataclass
class LauncherCodexCurrentPaneStarter:
    bind_target_fn: Callable[..., str | None]
    with_bin_path_env_fn: Callable[[], dict]
    provider_env_overrides_fn: Callable[[str], dict]
    run_shell_command_fn: Callable[..., int]
    build_pane_title_cmd_fn: Callable[[str], str]
    build_env_prefix_fn: Callable[[dict], str]
    export_path_builder_fn: Callable[[Path], str]
    build_codex_start_cmd_fn: Callable[[], str]
    write_codex_session_fn: Callable[..., bool]
    popen_fn: Callable[..., object] = subprocess.Popen
    mkfifo_fn: Callable[[str, int], None] = os.mkfifo
    stderr: TextIO = sys.stderr

    def start(
        self,
        *,
        runtime: Path,
        script_dir: Path,
        ccb_session_id: str,
        terminal_type: str | None,
        cwd: Path,
        display_label: str = 'Codex',
    ) -> int:
        input_fifo = runtime / 'input.fifo'
        output_fifo = runtime / 'output.fifo'
        label = str(display_label or '').strip() or 'Codex'
        pane_title_marker = f'CCB-{label}'
        start_cmd = self._start_cmd(
            script_dir=script_dir,
            terminal_type=terminal_type,
            pane_title_marker=pane_title_marker,
        )

        runtime.mkdir(parents=True, exist_ok=True)
        pane_id = self.bind_target_fn(
            runtime=runtime,
            pane_title_marker=pane_title_marker,
            agent_label=label,
            bind_session_fn=lambda bound_pane_id: self.write_codex_session_fn(
                runtime,
                None,
                input_fifo,
                output_fifo,
                pane_id=bound_pane_id,
                pane_title_marker=pane_title_marker,
                codex_start_cmd=start_cmd,
            ),
            display_label=label,
        )
        if not pane_id:
            return 1

        if terminal_type == 'tmux':
            self._ensure_fifo(input_fifo, 0o600)
            self._ensure_fifo(output_fifo, 0o644)

        if terminal_type == 'tmux':
            self._spawn_bridge(
                runtime=runtime,
                pane_id=pane_id,
                script_dir=script_dir,
            )

        if os.name == 'nt':
            env = self._codex_env(
                runtime=runtime,
                input_fifo=input_fifo,
                output_fifo=output_fifo,
                ccb_session_id=ccb_session_id,
                terminal_type=terminal_type,
                pane_id=pane_id,
            )
            return self.run_shell_command_fn(self.build_codex_start_cmd_fn(), env=env, cwd=str(cwd))

        env = self._codex_env(
            runtime=runtime,
            input_fifo=input_fifo,
            output_fifo=output_fifo,
            ccb_session_id=ccb_session_id,
            terminal_type=terminal_type,
            pane_id=pane_id,
        )
        try:
            proc = self.popen_fn(shlex.split(self.build_codex_start_cmd_fn()), env=env, cwd=str(cwd))
        except Exception as exc:
            print(f'❌ Failed to start Codex: {exc}', file=self.stderr)
            return 1

        try:
            if terminal_type == 'tmux':
                (runtime / 'codex.pid').write_text(str(proc.pid) + '\n', encoding='utf-8')
        except Exception:
            pass
        return proc.wait()

    def _start_cmd(self, *, script_dir: Path, terminal_type: str | None, pane_title_marker: str) -> str:
        del terminal_type, pane_title_marker
        return (
            self.build_env_prefix_fn(self.provider_env_overrides_fn('codex'))
            + self.export_path_builder_fn(script_dir / 'bin')
            + self.build_codex_start_cmd_fn()
        )

    def _ensure_fifo(self, path: Path, mode: int) -> None:
        if path.exists():
            return
        self.mkfifo_fn(str(path), mode)

    def _codex_env(
        self,
        *,
        runtime: Path,
        input_fifo: Path,
        output_fifo: Path,
        ccb_session_id: str,
        terminal_type: str | None,
        pane_id: str,
    ) -> dict:
        env = self.with_bin_path_env_fn()
        env.update(self.provider_env_overrides_fn('codex'))
        env['CCB_SESSION_ID'] = ccb_session_id
        env['CODEX_RUNTIME_DIR'] = str(runtime)
        env['CODEX_INPUT_FIFO'] = str(input_fifo)
        env['CODEX_OUTPUT_FIFO'] = str(output_fifo)
        env['CODEX_TERMINAL'] = terminal_type or 'tmux'
        env['CODEX_TMUX_SESSION'] = pane_id
        return env

    def _spawn_bridge(self, *, runtime: Path, pane_id: str, script_dir: Path) -> None:
        bridge_script = script_dir / 'lib' / 'provider_backends' / 'codex' / 'bridge.py'
        bridge_env = os.environ.copy()
        bridge_env['CODEX_TERMINAL'] = 'tmux'
        bridge_env['CODEX_TMUX_SESSION'] = pane_id
        bridge_env['CODEX_RUNTIME_DIR'] = str(runtime)
        bridge_env['CODEX_INPUT_FIFO'] = str(runtime / 'input.fifo')
        bridge_env['CODEX_OUTPUT_FIFO'] = str(runtime / 'output.fifo')
        bridge_env['CODEX_TMUX_LOG'] = str(runtime / 'bridge_output.log')
        bridge_env['PYTHONPATH'] = str(script_dir) + os.pathsep + bridge_env.get('PYTHONPATH', '')
        bridge_proc = self.popen_fn(
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
