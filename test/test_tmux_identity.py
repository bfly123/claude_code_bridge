from __future__ import annotations

from terminal_runtime.tmux_identity import pane_visual
from terminal_runtime.tmux_theme import render_tmux_session_theme


def test_pane_visual_is_stable_for_same_project_slot() -> None:
    first = pane_visual(project_id='proj-1', slot_key='agent3', order_index=2)
    second = pane_visual(project_id='proj-1', slot_key='agent3', order_index=99)
    assert first == second


def test_pane_visual_uses_different_palette_for_cmd_pool() -> None:
    cmd_visual = pane_visual(project_id='proj-1', slot_key='cmd', is_cmd=True)
    agent_visual = pane_visual(project_id='proj-1', slot_key='cmd', is_cmd=False)
    assert cmd_visual != agent_visual


def test_pane_visual_uses_order_index_when_slot_identity_missing() -> None:
    first = pane_visual(order_index=0)
    second = pane_visual(order_index=1)
    assert first != second


def test_render_tmux_session_theme_uses_terminal_profile_overrides() -> None:
    rendered = render_tmux_session_theme(
        ccb_version='9.9.9',
        status_script=None,
        git_script=None,
        environ={'TERM_PROGRAM': 'Apple_Terminal'},
    )
    assert rendered.profile_name == 'contrast'
    assert rendered.window_options['pane-border-style'] == 'fg=#565f89,bold'
    assert rendered.window_options['window-style'] == 'bg=#181825'
