from __future__ import annotations

import os
import time


def cleanup_launcher(
    launcher,
    *,
    tmux_backend_factory,
    translate_fn,
    cleanup_tmpclaude_fn,
    cleanup_stale_runtime_fn,
    shrink_logs_fn,
    shutil_module,
    quiet: bool = False,
    kill_panes: bool = True,
    clear_sessions: bool = True,
    remove_runtime: bool = True,
) -> None:
    if launcher._cleaned:
        return
    launcher._cleaned = True

    if not quiet:
        print(f"\n🧹 {translate_fn('cleaning_up')}")

    try:
        launcher._set_tmux_ui_active(False)
    except Exception:
        pass

    for fn in (cleanup_tmpclaude_fn, cleanup_stale_runtime_fn, shrink_logs_fn):
        try:
            fn()
        except Exception:
            pass

    if kill_panes:
        backend = tmux_backend_factory()
        pane_ids = list(launcher.tmux_panes.values()) + list(launcher.extra_panes.values())
        for pane_id in pane_ids:
            if pane_id:
                backend.kill_pane(pane_id)

    if clear_sessions:
        launcher.cleanup_coordinator.mark_project_sessions_inactive()

    launcher.cleanup_coordinator.shutdown_owned_ccbd()

    if remove_runtime and launcher.runtime_dir.exists():
        shutil_module.rmtree(launcher.runtime_dir, ignore_errors=True)

    if not quiet:
        print(f"✅ {translate_fn('cleanup_complete')}")


def run_up_launcher(
    launcher,
    *,
    version: str,
    script_dir,
    get_git_info_fn,
    plan_two_column_layout_fn,
    runup_coordinator_cls,
    cleanup_tmpclaude_fn,
    cleanup_stale_runtime_dirs_fn,
    shrink_logs_fn,
) -> int:
    git_info = get_git_info_fn(script_dir)
    version_str = f"v{version}" + (f" ({git_info})" if git_info else "")
    print(f"🚀 Claude Code Bridge {version_str}")
    print(f"📅 {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔌 Targets: {', '.join(launcher.target_names)}")
    print("=" * 50)
    launcher._sync_terminal_type_state()
    preflight = launcher.runup_preflight.prepare()
    if preflight.code is not None:
        launcher.terminal_type = preflight.terminal_type
        return preflight.code

    launcher.terminal_type = preflight.terminal_type
    launcher._sync_terminal_type_state()
    launcher.anchor_name = preflight.anchor_name
    launcher.anchor_pane_id = preflight.anchor_pane_id
    cmd_settings = preflight.cmd_settings or {}
    layout = preflight.layout or plan_two_column_layout_fn(anchor_name=launcher.anchor_name, spawn_items=[])

    cleanup_kwargs: dict[str, object] = {}
    coordinator = runup_coordinator_cls(
        target_names=tuple(launcher.target_names),
        anchor_name=launcher.anchor_name,
        anchor_pane_id=launcher.anchor_pane_id,
        terminal_type=launcher.terminal_type,
        cleanup_fn=launcher.cleanup,
        set_tmux_ui_active_fn=launcher._set_tmux_ui_active,
        set_current_pane_label_fn=launcher._set_current_pane_label,
        write_local_claude_session_fn=launcher._write_local_claude_session,
        read_local_claude_session_id_fn=launcher._read_local_claude_session_id,
        start_item_fn=lambda item, parent, direction: _start_item(
            launcher,
            item,
            parent=parent,
            direction=direction,
            cmd_settings=cmd_settings,
        ),
        sync_cend_registry_fn=launcher.session_gateway.sync_cend_registry,
        start_anchor_fn=launcher._start_provider_in_current_pane,
        cleanup_tmpclaude_fn=cleanup_tmpclaude_fn,
        cleanup_stale_runtime_fn=lambda: cleanup_stale_runtime_dirs_fn(exclude=launcher.runtime_dir),
        shrink_logs_fn=shrink_logs_fn,
        debug_enabled_fn=lambda: os.environ.get("CCB_DEBUG") in ("1", "true", "yes"),
    )

    coordinator.register_cleanup_handlers(cleanup_kwargs)
    coordinator.run_housekeeping()
    coordinator.activate_anchor()

    if not coordinator.launch_non_anchor(layout):
        return 1

    return coordinator.finish(cleanup_kwargs)


def _start_item(
    launcher,
    item: str,
    *,
    parent: str | None,
    direction: str | None,
    cmd_settings: dict,
) -> str | None:
    if item == "cmd":
        return launcher._start_cmd_pane(parent_pane=parent, direction=direction, cmd_settings=cmd_settings)
    if item == "claude":
        return launcher._start_claude_pane(parent_pane=parent, direction=direction)
    pane_id = launcher._start_provider(item, display_label=item, parent_pane=parent, direction=direction)
    if pane_id:
        launcher.warmup_service.warmup_provider(item)
    return pane_id
