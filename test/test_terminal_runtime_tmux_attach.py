from __future__ import annotations

from terminal_runtime.tmux_attach import normalize_user_option
from terminal_runtime.tmux_attach import pane_exists_output
from terminal_runtime.tmux_attach import pane_is_alive
from terminal_runtime.tmux_attach import pane_pipe_enabled
from terminal_runtime.tmux_attach import parse_session_name
from terminal_runtime.tmux_attach import should_attach_selected_pane


def test_tmux_attach_helpers() -> None:
    assert normalize_user_option("ccb_agent") == "@ccb_agent"
    assert normalize_user_option("@keep") == "@keep"
    assert normalize_user_option("") == ""
    assert pane_exists_output("%12\n") is True
    assert pane_exists_output("12\n") is False
    assert pane_pipe_enabled("1\n") is True
    assert pane_pipe_enabled("0\n") is False
    assert pane_is_alive("0\n") is True
    assert pane_is_alive("1\n") is False
    assert parse_session_name(" demo \n") == "demo"
    assert should_attach_selected_pane(env_tmux="") is True
    assert should_attach_selected_pane(env_tmux="/tmp/tmux") is False
