from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from launcher.codex_current_launcher import LauncherCodexCurrentPaneStarter


def test_codex_current_launcher_starts_tmux_runtime_and_records_pids(tmp_path: Path) -> None:
    bind_calls: list[dict] = []
    mkfifo_calls: list[tuple[str, int]] = []
    popen_calls: list[tuple[list[str], dict]] = []
    write_calls: list[dict] = []

    class _Proc:
        def __init__(self, pid: int, returncode: int = 0) -> None:
            self.pid = pid
            self._returncode = returncode

        def wait(self) -> int:
            return self._returncode

    proc_seq = [_Proc(9911), _Proc(4242, returncode=0)]

    def _popen(args, **kwargs):
        popen_calls.append((args, kwargs))
        return proc_seq.pop(0)

    def _bind_target(**kwargs):
        bind_calls.append(kwargs)
        kwargs['bind_session_fn']('%8')
        return '%8'

    launcher = LauncherCodexCurrentPaneStarter(
        bind_target_fn=_bind_target,
        with_bin_path_env_fn=lambda: {'PATH': '/tmp/bin'},
        provider_env_overrides_fn=lambda provider: {'CCB_CALLER': provider},
        run_shell_command_fn=lambda *args, **kwargs: 77,
        build_pane_title_cmd_fn=lambda title: f'title:{title}; ',
        build_env_prefix_fn=lambda env: 'export ENV=1; ',
        export_path_builder_fn=lambda path: f'export PATH={path}; ',
        build_codex_start_cmd_fn=lambda: 'codex -c disable_paste_burst=true',
        write_codex_session_fn=lambda runtime, tmux_session, input_fifo, output_fifo, **kwargs: write_calls.append(
            {
                'runtime': str(runtime),
                'input_fifo': str(input_fifo),
                'output_fifo': str(output_fifo),
                **kwargs,
            }
        ) or True,
        popen_fn=_popen,
        mkfifo_fn=lambda path, mode: mkfifo_calls.append((path, mode)) or Path(path).write_text('', encoding='utf-8'),
    )

    rc = launcher.start(
        runtime=tmp_path / 'codex-runtime',
        script_dir=tmp_path / 'repo',
        ccb_session_id='ai-9',
        terminal_type='tmux',
        cwd=tmp_path / 'repo',
        display_label='agent1',
    )

    assert rc == 0
    assert bind_calls[0]['display_label'] == 'agent1'
    assert bind_calls[0]['pane_title_marker'] == 'CCB-agent1'
    assert bind_calls[0]['agent_label'] == 'agent1'
    assert mkfifo_calls == [
        (str(tmp_path / 'codex-runtime' / 'input.fifo'), 0o600),
        (str(tmp_path / 'codex-runtime' / 'output.fifo'), 0o644),
    ]
    assert write_calls[0]['pane_id'] == '%8'
    assert write_calls[0]['pane_title_marker'] == 'CCB-agent1'
    assert (tmp_path / 'codex-runtime' / 'bridge.pid').read_text(encoding='utf-8').strip() == '9911'
    assert (tmp_path / 'codex-runtime' / 'codex.pid').read_text(encoding='utf-8').strip() == '4242'
    bridge_args, bridge_kwargs = popen_calls[0]
    assert bridge_args == [
        sys.executable,
        str(tmp_path / 'repo' / 'lib' / 'provider_backends' / 'codex' / 'bridge.py'),
        '--runtime-dir',
        str(tmp_path / 'codex-runtime'),
    ]
    assert 'CODEX_SESSION_ID' not in bridge_kwargs['env']
    assert bridge_kwargs['env']['CODEX_TMUX_SESSION'] == '%8'
    codex_args, codex_kwargs = popen_calls[1]
    assert codex_args == ['codex', '-c', 'disable_paste_burst=true']
    assert codex_kwargs['env']['CCB_SESSION_ID'] == 'ai-9'
    assert codex_kwargs['env']['CODEX_INPUT_FIFO'].endswith('input.fifo')
    assert codex_kwargs['env']['CODEX_TMUX_SESSION'] == '%8'
