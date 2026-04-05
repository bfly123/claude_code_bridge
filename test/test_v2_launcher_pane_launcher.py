from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from launcher.pane_launcher import LauncherTmuxPaneLauncher


class _FakeBackend:
    pass


def test_start_simple_target_uses_shared_tmux_spawn_and_session_writer(tmp_path: Path) -> None:
    calls: dict[str, object] = {}
    panes: dict[str, str] = {}

    def _spawn(backend, *, cwd, cmd, title, agent_label, existing_panes, direction, parent_pane):
        calls['spawn'] = {
            'cwd': str(cwd),
            'cmd': cmd,
            'title': title,
            'agent_label': agent_label,
            'direction': direction,
            'parent_pane': parent_pane,
            'existing_panes': existing_panes,
        }
        return '%9'

    def _write(runtime, tmux_session, *, pane_id=None, pane_title_marker=None, start_cmd=None):
        calls['write'] = {
            'runtime': str(runtime),
            'tmux_session': tmux_session,
            'pane_id': pane_id,
            'pane_title_marker': pane_title_marker,
            'start_cmd': start_cmd,
        }
        return True

    launcher = LauncherTmuxPaneLauncher(
        script_dir=tmp_path,
        tmux_panes=panes,
        backend_factory=_FakeBackend,
        spawn_tmux_pane_fn=_spawn,
    )

    pane_id = launcher.start_simple_target(
        target_key='gemini',
        runtime=tmp_path / 'runtime',
        cwd=tmp_path / 'repo',
        start_cmd='gemini --continue',
        pane_title_marker='CCB-Gemini',
        agent_label='Gemini',
        parent_pane='%1',
        direction='bottom',
        write_session_fn=_write,
    )

    assert pane_id == '%9'
    assert panes['gemini'] == '%9'
    assert calls['spawn']['agent_label'] == 'Gemini'
    assert calls['write']['pane_id'] == '%9'
    assert calls['write']['start_cmd'] == 'gemini --continue'


def test_start_codex_creates_fifos_spawns_bridge_and_writes_session(tmp_path: Path) -> None:
    calls: dict[str, object] = {}
    panes: dict[str, str] = {}

    def _spawn(backend, *, cwd, cmd, title, agent_label, existing_panes, direction, parent_pane):
        calls['spawn'] = {'cmd': cmd, 'title': title, 'agent_label': agent_label}
        return '%7'

    def _run(args, **kwargs):
        calls['run'] = {'args': args, 'kwargs': kwargs}
        return subprocess.CompletedProcess(args=args, returncode=0, stdout='4321\n', stderr='')

    class _Popen:
        def __init__(self, args, **kwargs):
            calls['popen'] = {'args': args, 'kwargs': kwargs}
            self.pid = 8765

    def _write(runtime, tmux_session, input_fifo, output_fifo, *, pane_id=None, pane_title_marker=None, codex_start_cmd=None):
        calls['write'] = {
            'runtime': str(runtime),
            'tmux_session': tmux_session,
            'input_fifo': str(input_fifo),
            'output_fifo': str(output_fifo),
            'pane_id': pane_id,
            'pane_title_marker': pane_title_marker,
            'codex_start_cmd': codex_start_cmd,
        }
        return True

    launcher = LauncherTmuxPaneLauncher(
        script_dir=tmp_path,
        tmux_panes=panes,
        backend_factory=_FakeBackend,
        spawn_tmux_pane_fn=_spawn,
        subprocess_run_fn=_run,
        subprocess_popen_fn=_Popen,
    )

    runtime = tmp_path / 'runtime-codex'
    pane_id = launcher.start_codex(
        runtime=runtime,
        cwd=tmp_path / 'repo',
        start_cmd='codex -c disable_paste_burst=true',
        pane_title_marker='CCB-Codex',
        agent_label='agent1',
        parent_pane=None,
        direction='right',
        write_session_fn=_write,
    )

    assert pane_id == '%7'
    assert panes['codex'] == '%7'
    assert (runtime / 'input.fifo').exists()
    assert (runtime / 'output.fifo').exists()
    assert (runtime / 'codex.pid').read_text(encoding='utf-8').strip() == '4321'
    assert (runtime / 'bridge.pid').read_text(encoding='utf-8').strip() == '8765'
    assert calls['write']['pane_id'] == '%7'
    assert calls['write']['codex_start_cmd'] == 'codex -c disable_paste_burst=true'
    assert calls['spawn']['agent_label'] == 'agent1'
    assert calls['popen']['kwargs']['env']['CODEX_TMUX_SESSION'] == '%7'
    assert 'CODEX_SESSION_ID' not in calls['popen']['kwargs']['env']
    assert calls['popen']['args'] == [
        sys.executable,
        str(tmp_path / 'lib' / 'provider_backends' / 'codex' / 'bridge.py'),
        '--runtime-dir',
        str(runtime),
    ]
