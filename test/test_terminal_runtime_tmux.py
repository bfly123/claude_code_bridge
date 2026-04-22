from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import terminal_runtime.tmux as tmux_module
from terminal_runtime.tmux import default_detached_session_name
from terminal_runtime.tmux import looks_like_pane_id
from terminal_runtime.tmux import looks_like_tmux_target
from terminal_runtime.tmux import normalize_socket_name
from terminal_runtime.tmux import normalize_split_direction
from terminal_runtime.tmux import pane_id_by_title_marker_output
from terminal_runtime.tmux import resolved_tmux_command
from terminal_runtime.tmux import socket_name_from_tmux_env
from terminal_runtime.tmux import tmux_base


def test_tmux_base_includes_socket_when_present() -> None:
    with patch.object(tmux_module, 'resolved_tmux_command', return_value=['tmux']):
        assert tmux_base(None) == ['tmux']
        assert tmux_base('ccb-demo') == ['tmux', '-L', 'ccb-demo']
        assert tmux_base('ccb-demo', socket_path='~/.tmux/demo.sock') == [
            'tmux',
            '-S',
            str(Path('~/.tmux/demo.sock').expanduser()),
        ]


def test_tmux_target_helpers() -> None:
    assert looks_like_pane_id('%1') is True
    assert looks_like_pane_id('sess') is False
    assert looks_like_tmux_target('%1') is True
    assert looks_like_tmux_target('sess:1.0') is True
    assert looks_like_tmux_target('sess') is False


def test_tmux_socket_name_helpers() -> None:
    assert normalize_socket_name(None) is None
    assert normalize_socket_name('') is None
    assert normalize_socket_name('default') is None
    assert normalize_socket_name('ccb') == 'ccb'
    assert socket_name_from_tmux_env(None) is None
    assert socket_name_from_tmux_env('') is None
    assert socket_name_from_tmux_env('/tmp/tmux-1000/default,123,0') is None
    assert socket_name_from_tmux_env('/tmp/tmux-1000/ccb,123,0') == 'ccb'


def test_normalize_split_direction() -> None:
    assert normalize_split_direction('right') == ('-h', 'right')
    assert normalize_split_direction('vertical') == ('-v', 'bottom')
    with pytest.raises(ValueError):
        normalize_split_direction('left')


def test_pane_id_by_title_marker_output_parses_list_panes() -> None:
    stdout = '%1\tCCB-a\n%2\tOTHER\n'
    assert pane_id_by_title_marker_output(stdout, 'CCB') == '%1'
    assert pane_id_by_title_marker_output(stdout, 'missing') is None


def test_pane_id_by_title_marker_output_rejects_ambiguous_prefix_matches() -> None:
    stdout = '%1\tCCB-codex-a1b2c3d4\n%2\tCCB-codex-e5f6g7h8\n'
    assert pane_id_by_title_marker_output(stdout, 'CCB-codex') is None


def test_pane_id_by_title_marker_output_prefers_unique_exact_match() -> None:
    stdout = '%1\tCCB-codex\n%2\tCCB-codex-a1b2c3d4\n'
    assert pane_id_by_title_marker_output(stdout, 'CCB-codex') == '%1'


def test_default_detached_session_name_is_stable_format() -> None:
    name = default_detached_session_name(cwd='/tmp/demo', pid=123, now_ts=1700000000.0)
    assert name == 'ccb-demo-0-123'


def test_resolved_tmux_command_uses_cmd_wrapper_for_windows_batch_tmux() -> None:
    command = resolved_tmux_command(
        which_fn=lambda name: r'C:\tools\tmux.cmd' if name == 'tmux' else None,
        os_name='nt',
        comspec=r'C:\Windows\System32\cmd.exe',
    )

    assert command == [r'C:\Windows\System32\cmd.exe', '/c', r'C:\tools\tmux.cmd']


def test_resolved_tmux_command_prefers_real_executable_without_wrapper() -> None:
    command = resolved_tmux_command(
        which_fn=lambda name: r'C:\tools\tmux.exe' if name == 'tmux' else None,
        os_name='nt',
    )

    assert command == [r'C:\tools\tmux.exe']


def test_tmux_base_appends_socket_args_after_windows_wrapper() -> None:
    with patch.object(tmux_module, 'resolved_tmux_command', return_value=['cmd.exe', '/c', r'C:\tools\tmux.cmd']):
        base = tmux_base(socket_path=r'C:\tmp\ccb\tmux.sock')

    assert base == ['cmd.exe', '/c', r'C:\tools\tmux.cmd', '-S', r'C:\tmp\ccb\tmux.sock']
