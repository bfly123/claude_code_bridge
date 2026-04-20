from __future__ import annotations

import os
from dataclasses import dataclass

from terminal_runtime.env import default_shell as _default_shell_impl
from terminal_runtime.env import env_float as _env_float_impl
from terminal_runtime.env import is_windows as _is_windows_impl
from terminal_runtime.env import is_wsl as _is_wsl_impl
from terminal_runtime.pane_logs import cleanup_pane_logs as _cleanup_pane_logs_impl
from terminal_runtime.pane_logs import maybe_trim_log as _maybe_trim_log_impl
from terminal_runtime.pane_logs import pane_log_path_for as _pane_log_path_for_impl
from terminal_runtime.tmux import normalize_split_direction as _normalize_split_direction_impl
from terminal_runtime.tmux import pane_id_by_title_marker_output as _tmux_pane_id_by_title_marker_output_impl
from terminal_runtime.tmux_attach import normalize_user_option as _normalize_tmux_user_option_impl
from terminal_runtime.tmux_attach import pane_exists_output as _tmux_pane_exists_output_impl
from terminal_runtime.tmux_attach import pane_is_alive as _tmux_pane_is_alive_impl
from terminal_runtime.tmux_attach import pane_pipe_enabled as _tmux_pane_pipe_enabled_impl
from terminal_runtime.tmux_input import build_buffer_name as _build_tmux_buffer_name_impl
from terminal_runtime.tmux_input import sanitize_text as _sanitize_tmux_text_impl
from terminal_runtime.tmux_input import should_use_inline_legacy_send as _should_use_inline_legacy_tmux_send_impl
from terminal_runtime.tmux_logs import TmuxPaneLogManager
from terminal_runtime.tmux_panes import TmuxPaneService
from terminal_runtime.tmux_respawn import append_stderr_redirection as _append_tmux_stderr_redirection_impl
from terminal_runtime.tmux_respawn import build_respawn_tmux_args as _build_tmux_respawn_tmux_args_impl
from terminal_runtime.tmux_respawn import build_shell_command as _build_tmux_shell_command_impl
from terminal_runtime.tmux_respawn import normalize_start_dir as _normalize_tmux_start_dir_impl
from terminal_runtime.tmux_respawn import resolve_shell as _resolve_tmux_shell_impl
from terminal_runtime.tmux_respawn import resolve_shell_flags as _resolve_tmux_shell_flags_impl
from terminal_runtime.tmux_respawn_service import TmuxRespawnService
from terminal_runtime.tmux_send import TmuxTextSender


@dataclass(frozen=True)
class TmuxBackendServices:
    pane_log_manager: TmuxPaneLogManager
    text_sender: TmuxTextSender
    pane_service: TmuxPaneService
    respawn_service: TmuxRespawnService


def build_pane_log_manager(backend) -> TmuxPaneLogManager:
    return TmuxPaneLogManager(
        socket_name=backend._socket_name,
        tmux_run_fn=lambda *args, **kwargs: backend._tmux_run(*args, **kwargs),
        is_alive_fn=backend.is_alive,
        pane_pipe_enabled_fn=_tmux_pane_pipe_enabled_impl,
        pane_log_path_for_fn=lambda pane_id, backend_name, socket_name: _pane_log_path_for_impl(
            pane_id, backend_name, socket_name
        ),
        cleanup_pane_logs_fn=_cleanup_pane_logs_impl,
        maybe_trim_log_fn=_maybe_trim_log_impl,
        pane_log_info=backend._pane_log_info,
    )


def build_text_sender(backend) -> TmuxTextSender:
    return TmuxTextSender(
        tmux_run_fn=lambda *args, **kwargs: backend._tmux_run(*args, **kwargs),
        looks_like_tmux_target_fn=backend._looks_like_tmux_target,
        ensure_not_in_copy_mode_fn=backend._ensure_not_in_copy_mode,
        build_buffer_name_fn=_build_tmux_buffer_name_impl,
        sanitize_text_fn=_sanitize_tmux_text_impl,
        should_use_inline_legacy_send_fn=_should_use_inline_legacy_tmux_send_impl,
        env_float_fn=_env_float,
    )


def build_pane_service(backend) -> TmuxPaneService:
    return TmuxPaneService(
        tmux_run_fn=lambda *args, **kwargs: backend._tmux_run(*args, **kwargs),
        looks_like_pane_id_fn=backend._looks_like_pane_id,
        normalize_split_direction_fn=_normalize_split_direction_impl,
        pane_exists_output_fn=_tmux_pane_exists_output_impl,
        pane_id_by_title_marker_output_fn=_tmux_pane_id_by_title_marker_output_impl,
        pane_is_alive_fn=_tmux_pane_is_alive_impl,
        normalize_user_option_fn=_normalize_tmux_user_option_impl,
        strip_ansi_fn=lambda text: backend._ANSI_RE.sub("", text),
    )


def build_respawn_service(backend) -> TmuxRespawnService:
    return TmuxRespawnService(
        tmux_run_fn=lambda *args, **kwargs: backend._tmux_run(*args, **kwargs),
        ensure_pane_log_fn=backend.ensure_pane_log,
        normalize_start_dir_fn=_normalize_tmux_start_dir_impl,
        append_stderr_redirection_fn=_append_tmux_stderr_redirection_impl,
        resolve_shell_fn=_resolve_tmux_shell_impl,
        resolve_shell_flags_fn=_resolve_tmux_shell_flags_impl,
        build_shell_command_fn=_build_tmux_shell_command_impl,
        build_respawn_tmux_args_fn=_build_tmux_respawn_tmux_args_impl,
        default_shell_fn=_default_shell,
        env=os.environ,
    )


def _default_shell() -> tuple[str, str]:
    return _default_shell_impl(is_wsl_fn=_is_wsl_impl, is_windows_fn=_is_windows_impl)


def _env_float(name: str, default: float) -> float:
    return _env_float_impl(name, default)


def build_backend_services(backend) -> TmuxBackendServices:
    pane_log_manager = build_pane_log_manager(backend)
    pane_service = build_pane_service(backend)
    text_sender = build_text_sender(backend)
    respawn_service = build_respawn_service(backend)
    return TmuxBackendServices(
        pane_log_manager=pane_log_manager,
        text_sender=text_sender,
        pane_service=pane_service,
        respawn_service=respawn_service,
    )


__all__ = [
    "TmuxBackendServices",
    "build_backend_services",
    "build_pane_log_manager",
    "build_pane_service",
    "build_respawn_service",
    "build_text_sender",
]
