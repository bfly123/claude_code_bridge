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
        raise RuntimeError("❌ No active Codex session found. Run 'ccb codex' (or add codex to ccb.config) first")

    comm.ccb_session_id = comm.session_info["ccb_session_id"]
    comm.runtime_dir = Path(comm.session_info["runtime_dir"])
    comm.input_fifo = Path(comm.session_info["input_fifo"])
    comm.terminal = comm.session_info.get("terminal", os.environ.get("CODEX_TERMINAL", "tmux"))
    comm.pane_id = get_pane_id_from_session_fn(comm.session_info) or ""
    comm.pane_title_marker = comm.session_info.get("pane_title_marker") or ""
    comm.backend = get_backend_for_session_fn(comm.session_info)

    comm.timeout = int(os.environ.get("CODEX_SYNC_TIMEOUT", "30"))
    comm.marker_prefix = provider_marker_prefix("codex")
    comm.project_session_file = comm.session_info.get("_session_file")
    comm._pane_health_cache = None
    comm._pane_health_ttl = max(0.0, pane_health_ttl)

    comm._log_reader = None
    comm._log_reader_primed = False


def ensure_log_reader(comm, *, log_reader_cls) -> None:
    if comm._log_reader is not None:
        return
    preferred_log = comm.session_info.get("codex_session_path")
    bound_session_id = comm.session_info.get("codex_session_id")
    work_dir_raw = str(comm.session_info.get("work_dir") or "").strip()
    work_dir = Path(work_dir_raw).expanduser() if work_dir_raw else None
    comm._log_reader = log_reader_cls(
        log_path=preferred_log,
        session_id_filter=bound_session_id,
        work_dir=work_dir,
        follow_workspace_sessions=True,
    )
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

    try:
        log_path_obj = log_path if isinstance(log_path, Path) else Path(str(log_path)).expanduser()
    except Exception:
        return

    comm.log_reader.set_preferred_log(log_path_obj)

    if not comm.project_session_file:
        return
    binding = update_project_session_binding_fn(
        project_file=Path(comm.project_session_file),
        log_path=log_path_obj,
        session_info=comm.session_info,
        debug_enabled=debug_enabled,
    )
    if binding is None:
        return

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
