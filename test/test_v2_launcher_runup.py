from __future__ import annotations

from launcher.runup import LauncherRunUpCoordinator, plan_two_column_layout


def test_plan_two_column_layout_balances_spawn_items() -> None:
    layout = plan_two_column_layout(anchor_name='codex', spawn_items=['gemini', 'opencode', 'claude'])

    assert layout.left_items == ('codex', 'opencode')
    assert layout.right_items == ('gemini', 'claude')


def test_runup_coordinator_launches_right_then_left_then_right_tail() -> None:
    launched: list[tuple[str, str | None, str | None]] = []
    cleanup_calls: list[dict] = []
    coordinator = LauncherRunUpCoordinator(
        target_names=('codex', 'gemini', 'opencode'),
        anchor_name='codex',
        anchor_pane_id='%1',
        terminal_type='tmux',
        cleanup_fn=lambda **kwargs: cleanup_calls.append(kwargs),
        set_tmux_ui_active_fn=lambda active: None,
        set_current_pane_label_fn=lambda provider: None,
        write_local_claude_session_fn=lambda **kwargs: None,
        read_local_claude_session_id_fn=lambda: None,
        start_item_fn=lambda item, parent, direction: launched.append((item, parent, direction)) or f'%{len(launched)+1}',
        sync_cend_registry_fn=lambda: None,
        start_anchor_fn=lambda provider: 0,
        cleanup_tmpclaude_fn=lambda: 0,
        cleanup_stale_runtime_fn=lambda: 0,
        shrink_logs_fn=lambda: 0,
        debug_enabled_fn=lambda: False,
    )

    ok = coordinator.launch_non_anchor(
        plan_two_column_layout(anchor_name='codex', spawn_items=['gemini', 'opencode', 'claude'])
    )

    assert ok is True
    assert launched == [
        ('gemini', '%1', 'right'),
        ('opencode', '%1', 'bottom'),
        ('claude', '%2', 'bottom'),
    ]


def test_runup_coordinator_finish_prepares_codex_runtime_for_non_anchor_codex() -> None:
    calls: list[str] = []
    cleanup_calls: list[dict] = []
    coordinator = LauncherRunUpCoordinator(
        target_names=('gemini', 'codex'),
        anchor_name='gemini',
        anchor_pane_id='%1',
        terminal_type='tmux',
        cleanup_fn=lambda **kwargs: cleanup_calls.append(kwargs),
        set_tmux_ui_active_fn=lambda active: None,
        set_current_pane_label_fn=lambda provider: None,
        write_local_claude_session_fn=lambda **kwargs: None,
        read_local_claude_session_id_fn=lambda: None,
        start_item_fn=lambda item, parent, direction: '%2',
        sync_cend_registry_fn=lambda: calls.append('sync'),
        start_anchor_fn=lambda provider: calls.append(f'anchor:{provider}') or 0,
        cleanup_tmpclaude_fn=lambda: 0,
        cleanup_stale_runtime_fn=lambda: 0,
        shrink_logs_fn=lambda: 0,
        debug_enabled_fn=lambda: False,
    )

    rc = coordinator.finish({})

    assert rc == 0
    assert calls == ['sync', 'anchor:gemini']
    assert cleanup_calls == [{}]
