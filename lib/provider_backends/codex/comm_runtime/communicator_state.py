from __future__ import annotations

import os
from pathlib import Path

from provider_core.runtime_specs import provider_marker_prefix


def initialize_state(
    comm,
    *,
    get_pane_id_from_session_fn,
    get_backend_for_session_fn,
    pane_health_ttl: float,
) -> None:
    comm.session_info = comm._load_session_info()
    if not comm.session_info:
        raise RuntimeError(
            "❌ No active Codex session found. "
            "Run 'ccb codex' (or add codex to ccb.config) first"
        )

    _assign_runtime_state(
        comm,
        get_pane_id_from_session_fn=get_pane_id_from_session_fn,
        get_backend_for_session_fn=get_backend_for_session_fn,
    )
    _assign_runtime_defaults(comm, pane_health_ttl=pane_health_ttl)


def ensure_log_reader(comm, *, log_reader_cls) -> None:
    if comm._log_reader is not None:
        return
    comm._log_reader = log_reader_cls(**_log_reader_kwargs(comm))
    if not comm._log_reader_primed:
        comm._prime_log_binding()
        comm._log_reader_primed = True


def prime_log_binding(comm) -> None:
    log_hint = comm.log_reader.current_log_path()
    if not log_hint:
        return
    comm._remember_codex_session(log_hint)


def remember_codex_session(
    comm,
    log_path: Path | None,
    *,
    update_project_session_binding_fn,
    publish_registry_binding_fn,
    debug_enabled: bool,
) -> None:
    if not log_path:
        log_path = comm.log_reader.current_log_path()
        if not log_path:
            return

    log_path_obj = _log_path_object(log_path)
    if log_path_obj is None:
        return

    comm.log_reader.set_preferred_log(log_path_obj)

    if not comm.project_session_file:
        return
    binding = _updated_project_binding(
        comm,
        log_path_obj=log_path_obj,
        update_project_session_binding_fn=update_project_session_binding_fn,
        debug_enabled=debug_enabled,
    )
    if binding is None:
        return

    _publish_binding(
        comm,
        binding=binding,
        publish_registry_binding_fn=publish_registry_binding_fn,
    )
    _update_session_info_from_binding(comm, binding=binding)


def _assign_runtime_state(
    comm,
    *,
    get_pane_id_from_session_fn,
    get_backend_for_session_fn,
) -> None:
    comm.ccb_session_id = comm.session_info["ccb_session_id"]
    comm.runtime_dir = Path(comm.session_info["runtime_dir"])
    comm.input_fifo = Path(comm.session_info["input_fifo"])
    comm.terminal = _terminal_name(comm.session_info)
    comm.pane_id = get_pane_id_from_session_fn(comm.session_info) or ""
    comm.pane_title_marker = comm.session_info.get("pane_title_marker") or ""
    comm.backend = get_backend_for_session_fn(comm.session_info)


def _assign_runtime_defaults(comm, *, pane_health_ttl: float) -> None:
    comm.timeout = int(os.environ.get("CODEX_SYNC_TIMEOUT", "30"))
    comm.marker_prefix = provider_marker_prefix("codex")
    comm.project_session_file = comm.session_info.get("_session_file")
    comm._pane_health_cache = None
    comm._pane_health_ttl = max(0.0, pane_health_ttl)
    comm._log_reader = None
    comm._log_reader_primed = False


def _terminal_name(session_info: dict) -> str:
    return session_info.get("terminal", os.environ.get("CODEX_TERMINAL", "tmux"))


def _log_reader_kwargs(comm) -> dict[str, object]:
    return {
        "log_path": comm.session_info.get("codex_session_path"),
        "session_id_filter": comm.session_info.get("codex_session_id"),
        "work_dir": _work_dir_path(comm.session_info),
        "follow_workspace_sessions": True,
    }


def _work_dir_path(session_info: dict) -> Path | None:
    work_dir_raw = str(session_info.get("work_dir") or "").strip()
    if not work_dir_raw:
        return None
    return Path(work_dir_raw).expanduser()


def _log_path_object(log_path: Path | str | None) -> Path | None:
    if log_path is None:
        return None
    try:
        if isinstance(log_path, Path):
            return log_path
        return Path(str(log_path)).expanduser()
    except Exception:
        return None


def _updated_project_binding(
    comm,
    *,
    log_path_obj: Path,
    update_project_session_binding_fn,
    debug_enabled: bool,
):
    binding = update_project_session_binding_fn(
        project_file=Path(comm.project_session_file),
        log_path=log_path_obj,
        session_info=comm.session_info,
        debug_enabled=debug_enabled,
    )
    if binding is None:
        return
    return binding


def _publish_binding(
    comm,
    *,
    binding,
    publish_registry_binding_fn,
) -> None:
    publish_registry_binding_fn(
        ccb_session_id=comm.ccb_session_id,
        ccb_project_id=binding.ccb_project_id,
        work_dir=comm.session_info.get("work_dir"),
        terminal=comm.terminal,
        pane_id=comm.pane_id or None,
        pane_title_marker=comm.pane_title_marker or None,
        session_file=comm.project_session_file,
        codex_session_id=binding.session_id,
        codex_session_path=binding.path_str,
    )


def _update_session_info_from_binding(comm, *, binding) -> None:
    comm.session_info["codex_session_path"] = binding.path_str
    if binding.session_id:
        comm.session_info["codex_session_id"] = binding.session_id
    if binding.resume_cmd:
        comm.session_info["codex_start_cmd"] = binding.resume_cmd
    if binding.start_cmd:
        comm.session_info["start_cmd"] = binding.start_cmd


__all__ = [
    "ensure_log_reader",
    "initialize_state",
    "prime_log_binding",
    "remember_codex_session",
]
