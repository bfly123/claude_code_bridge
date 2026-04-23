from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def _run_tmux(bin_path: Path, state_dir: Path, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env['CCB_FAKE_TMUX_STATE_DIR'] = str(state_dir)
    return subprocess.run(
        [sys.executable, str(bin_path), *args],
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def test_fake_tmux_session_pane_and_window_roundtrip(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parent / 'fixtures' / 'fake_tmux.py'
    state_dir = tmp_path / 'state'

    created = _run_tmux(script, state_dir, 'new-session', '-d', '-s', 'demo', '-n', 'work')
    assert created.returncode == 0

    panes = _run_tmux(script, state_dir, 'list-panes', '-t', 'demo', '-F', '#{pane_id}')
    assert panes.returncode == 0
    assert panes.stdout.strip() == '%1'

    split = _run_tmux(script, state_dir, 'split-window', '-h', '-l', '80', '-t', '%1', '-P', '-F', '#{pane_id}')
    assert split.returncode == 0
    assert split.stdout.strip() == '%2'

    set_opt = _run_tmux(script, state_dir, 'set-option', '-p', '-t', '%2', '@ccb-agent', 'demo')
    assert set_opt.returncode == 0

    described = _run_tmux(
        script,
        state_dir,
        'display-message',
        '-p',
        '-t',
        '%2',
        '#{pane_id}\t#{pane_dead}\t#{@ccb-agent}',
    )
    assert described.returncode == 0
    assert described.stdout.strip() == '%2\t0\tdemo'

    new_window = _run_tmux(script, state_dir, 'new-window', '-d', '-t', 'demo', '-n', 'ws2')
    assert new_window.returncode == 0

    windows = _run_tmux(script, state_dir, 'list-windows', '-t', 'demo', '-F', '#{window_name}')
    assert windows.returncode == 0
    assert windows.stdout.splitlines() == ['work', 'ws2']


def test_fake_tmux_buffers_and_capture_pane(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parent / 'fixtures' / 'fake_tmux.py'
    state_dir = tmp_path / 'state'
    assert _run_tmux(script, state_dir, 'new-session', '-d', '-s', 'demo').returncode == 0
    assert _run_tmux(script, state_dir, 'load-buffer', '-b', 'buf1', '-', input_text='hello').returncode == 0
    assert _run_tmux(script, state_dir, 'paste-buffer', '-p', '-t', '%1', '-b', 'buf1').returncode == 0
    assert _run_tmux(script, state_dir, 'send-keys', '-t', '%1', 'Enter').returncode == 0

    captured = _run_tmux(script, state_dir, 'capture-pane', '-t', '%1', '-p', '-S', '-20')
    assert captured.returncode == 0
    assert captured.stdout.strip() == 'hello'


def test_fake_tmux_display_message_missing_pane_fails(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parent / 'fixtures' / 'fake_tmux.py'
    state_dir = tmp_path / 'state'

    assert _run_tmux(script, state_dir, 'new-session', '-d', '-s', 'demo').returncode == 0

    missing = _run_tmux(script, state_dir, 'display-message', '-p', '-t', '%99', '#{pane_dead}')

    assert missing.returncode == 1
    assert missing.stdout.strip() == ''


def test_fake_tmux_reports_active_pane_and_pane_pid(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parent / 'fixtures' / 'fake_tmux.py'
    state_dir = tmp_path / 'state'

    assert _run_tmux(script, state_dir, 'new-session', '-d', '-s', 'demo').returncode == 0
    split = _run_tmux(script, state_dir, 'split-window', '-h', '-t', '%1', '-P', '-F', '#{pane_id}')
    assert split.returncode == 0
    active_pane = split.stdout.strip()

    listed = _run_tmux(script, state_dir, 'list-panes', '-t', 'demo', '-F', '#{?pane_active,#{pane_id},}')
    active_lines = [line.strip() for line in listed.stdout.splitlines() if line.strip()]
    assert active_lines == [active_pane]

    pane_pid = _run_tmux(script, state_dir, 'display-message', '-p', '-t', active_pane, '#{pane_pid}')
    assert pane_pid.returncode == 0
    assert pane_pid.stdout.strip().isdigit()


def test_fake_tmux_persists_window_options_and_hooks(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parent / 'fixtures' / 'fake_tmux.py'
    state_dir = tmp_path / 'state'

    assert _run_tmux(script, state_dir, 'new-session', '-d', '-s', 'demo').returncode == 0
    assert _run_tmux(script, state_dir, 'set-window-option', '-t', 'demo', 'pane-border-status', 'top').returncode == 0
    assert _run_tmux(script, state_dir, 'set-hook', '-t', 'demo', 'after-select-pane', 'echo ok').returncode == 0

    state = json.loads((state_dir / 'fake-tmux-state.json').read_text(encoding='utf-8'))
    server = next(iter(state['servers'].values()))
    session = server['sessions']['demo']
    window = next(iter(session['windows'].values()))

    assert window['options']['pane-border-status'] == 'top'
    assert session['hooks']['after-select-pane'] == 'echo ok'


def test_fake_tmux_socket_path_is_case_normalized_on_windows(tmp_path: Path) -> None:
    if os.name != 'nt':
        return
    script = Path(__file__).resolve().parent / 'fixtures' / 'fake_tmux.py'
    state_dir = tmp_path / 'state'
    socket_path = tmp_path / 'SockDir' / 'demo.sock'

    created = _run_tmux(script, state_dir, '-S', str(socket_path), 'new-session', '-d', '-s', 'demo')
    assert created.returncode == 0

    listed = _run_tmux(script, state_dir, '-S', str(socket_path).upper(), 'list-sessions', '-F', '#{session_name}')
    assert listed.returncode == 0
    assert listed.stdout.strip() == 'demo'
