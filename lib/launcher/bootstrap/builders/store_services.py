from __future__ import annotations


def build_store_services(
    launcher,
    *,
    claude_local_session_store_cls,
    target_session_store_cls,
    session_gateway_cls,
    check_session_writable_fn,
    safe_write_session_fn,
    normalize_path_for_match_fn,
    extract_session_work_dir_norm_fn,
    work_dir_match_keys_fn,
    upsert_registry_fn,
    compute_project_id_fn,
    read_session_json_fn,
) -> None:
    launcher.claude_session_store = claude_local_session_store_cls(
        session_path=launcher._project_session_file(".claude-session"),
        project_root=launcher.project_root,
        invocation_dir=launcher.invocation_dir,
        ccb_session_id=launcher.ccb_session_id,
        project_id=launcher.project_id,
        default_terminal=launcher.terminal_type,
        check_session_writable_fn=check_session_writable_fn,
        safe_write_session_fn=safe_write_session_fn,
        normalize_path_for_match_fn=normalize_path_for_match_fn,
        extract_session_work_dir_norm_fn=extract_session_work_dir_norm_fn,
        work_dir_match_keys_fn=work_dir_match_keys_fn,
        upsert_registry_fn=upsert_registry_fn,
    )
    launcher.target_session_store = target_session_store_cls(
        project_root=launcher.project_root,
        invocation_dir=launcher.invocation_dir,
        ccb_session_id=launcher.ccb_session_id,
        terminal_type=launcher.terminal_type,
        project_session_path_fn=launcher._project_session_file,
        compute_project_id_fn=compute_project_id_fn,
        normalize_path_for_match_fn=normalize_path_for_match_fn,
        check_session_writable_fn=check_session_writable_fn,
        safe_write_session_fn=safe_write_session_fn,
        read_session_json_fn=read_session_json_fn,
        upsert_registry_fn=upsert_registry_fn,
        clear_codex_log_binding_fn=launcher._clear_codex_log_binding,
    )
    launcher.session_gateway = session_gateway_cls(
        target_session_store=launcher.target_session_store,
        target_names=tuple(launcher.target_names),
        provider_pane_id_fn=launcher._provider_pane_id,
        resume=launcher.resume,
    )
