from __future__ import annotations

import subprocess
from pathlib import Path

from terminal_runtime.tmux_logs import TmuxPaneLogManager


def _cp(*, stdout: str = '', returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=['tmux'], returncode=returncode, stdout=stdout, stderr='')


def test_tmux_pane_log_manager_ensures_log_and_tracks_info(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    pane_log_info: dict[str, float] = {}
    manager = TmuxPaneLogManager(
        socket_name='sock',
        tmux_run_fn=lambda args, **kwargs: calls.append(args) or _cp(),
        is_alive_fn=lambda pane_id: True,
        pane_pipe_enabled_fn=lambda output: False,
        pane_log_path_for_fn=lambda pane_id, backend, socket_name: tmp_path / f'{pane_id}.log',
        cleanup_pane_logs_fn=lambda path: None,
        maybe_trim_log_fn=lambda path: None,
        time_fn=lambda: 12.5,
        pane_log_info=pane_log_info,
    )

    log_path = manager.ensure_pane_log('%1')

    assert log_path == tmp_path / '%1.log'
    assert calls == [['pipe-pane', '-o', '-t', '%1', f'tee -a {tmp_path / "%1.log"}']]
    assert pane_log_info == {'%1': 12.5}


def test_tmux_pane_log_manager_refreshes_only_when_pipe_missing(tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict]] = []
    ensured: list[str] = []
    pane_log_info = {'%1': 1.0, '%2': 2.0}

    def tmux_run(args, **kwargs):
        calls.append((args, kwargs))
        if args == ['display-message', '-p', '-t', '%1', '#{pane_pipe}']:
            return _cp(stdout='0\n')
        if args == ['display-message', '-p', '-t', '%2', '#{pane_pipe}']:
            return _cp(stdout='1\n')
        return _cp()

    manager = TmuxPaneLogManager(
        socket_name=None,
        tmux_run_fn=tmux_run,
        is_alive_fn=lambda pane_id: True,
        pane_pipe_enabled_fn=lambda output: output.strip() == '1',
        pane_log_path_for_fn=lambda pane_id, backend, socket_name: tmp_path / f'{pane_id}.log',
        cleanup_pane_logs_fn=lambda path: None,
        maybe_trim_log_fn=lambda path: None,
        pane_log_info=pane_log_info,
    )
    manager.ensure_pane_log = lambda pane_id: ensured.append(pane_id) or (tmp_path / f'{pane_id}.log')  # type: ignore[method-assign]

    manager.refresh_pane_logs()

    assert ensured == ['%1']


def test_tmux_pane_log_manager_skips_dead_panes_during_refresh(tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict]] = []
    manager = TmuxPaneLogManager(
        socket_name=None,
        tmux_run_fn=lambda args, **kwargs: calls.append((args, kwargs)) or _cp(stdout='0\n'),
        is_alive_fn=lambda pane_id: False,
        pane_pipe_enabled_fn=lambda output: False,
        pane_log_path_for_fn=lambda pane_id, backend, socket_name: tmp_path / f'{pane_id}.log',
        cleanup_pane_logs_fn=lambda path: None,
        maybe_trim_log_fn=lambda path: None,
        pane_log_info={'%1': 1.0},
    )

    manager.refresh_pane_logs()

    assert calls == []
