from __future__ import annotations

from terminal_runtime.tmux_identity import pane_visual


def test_pane_visual_is_stable_for_same_project_slot() -> None:
    first = pane_visual(project_id='proj-1', slot_key='agent3', order_index=2)
    second = pane_visual(project_id='proj-1', slot_key='agent3', order_index=99)
    assert first == second


def test_pane_visual_uses_different_palette_for_cmd_pool() -> None:
    cmd_visual = pane_visual(project_id='proj-1', slot_key='cmd', is_cmd=True)
    agent_visual = pane_visual(project_id='proj-1', slot_key='cmd', is_cmd=False)
    assert cmd_visual != agent_visual

