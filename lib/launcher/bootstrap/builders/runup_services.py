from __future__ import annotations

import sys


def build_runup_services(
    launcher,
    *,
    cleanup_coordinator_cls,
    target_router_cls,
    runup_preflight_cls,
    warmup_service_cls,
    mark_session_inactive_fn,
    safe_write_session_fn,
    translate_fn,
    subprocess_module,
) -> None:
    launcher.cleanup_coordinator = cleanup_coordinator_cls(
        ccb_pid=launcher.ccb_pid,
        project_session_paths=(
            launcher._project_session_file(".codex-session"),
            launcher._project_session_file(".gemini-session"),
            launcher._project_session_file(".opencode-session"),
            launcher._project_session_file(".claude-session"),
            launcher._project_session_file(".droid-session"),
        ),
        mark_session_inactive_fn=mark_session_inactive_fn,
        safe_write_session_fn=safe_write_session_fn,
    )
    launcher.target_router = target_router_cls(
        terminal_type=launcher.terminal_type,
        target_tmux_starters={
            "codex": launcher._start_codex_tmux,
            "gemini": launcher._start_gemini_tmux,
            "opencode": launcher._start_opencode_tmux,
            "droid": launcher._start_droid_tmux,
        },
        translate_fn=translate_fn,
        stderr=sys.stderr,
    )
    launcher.runup_preflight = runup_preflight_cls(
        target_names=tuple(launcher.target_names),
        terminal_type=launcher.terminal_type,
        require_project_config_dir_fn=launcher._require_project_config_dir,
        backfill_claude_session_fn=launcher._backfill_claude_session_work_dir_fields,
        current_pane_id_fn=launcher._current_pane_id,
        cmd_settings_fn=launcher._cmd_settings,
        translate_fn=translate_fn,
        stderr=sys.stderr,
    )
    launcher.warmup_service = warmup_service_cls()
