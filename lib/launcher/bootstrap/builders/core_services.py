from __future__ import annotations


def build_core_services(
    launcher,
    *,
    start_command_factory_cls,
    normalize_path_for_match_fn,
    normpath_within_fn,
    build_cd_cmd_fn,
    translate_fn,
) -> None:
    launcher.start_command_factory = start_command_factory_cls(
        project_root=launcher.project_root,
        invocation_dir=launcher.invocation_dir,
        resume=launcher.resume,
        auto=launcher.auto,
        project_session_path_fn=launcher._project_session_file,
        normalize_path_for_match_fn=normalize_path_for_match_fn,
        normpath_within_fn=normpath_within_fn,
        build_cd_cmd_fn=build_cd_cmd_fn,
        translate_fn=translate_fn,
    )
