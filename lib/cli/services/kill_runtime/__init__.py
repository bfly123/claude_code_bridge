from __future__ import annotations

from .agent_cleanup import KillPreparation, collect_candidate_tmux_sockets, extra_agent_dir_names, prepare_local_shutdown
from .finalize import finalize_kill
from .lifecycle import destroy_project_namespace
from .pid_cleanup import (
    collect_agent_pid_candidates,
    coerce_pid,
    path_within,
    pid_matches_project,
    read_pid_file,
    read_proc_cmdline,
    read_proc_path,
    remove_pid_files,
    terminate_runtime_pids,
)
from .remote import await_remote_shutdown, request_remote_stop, resolve_shutdown_summary
from .reporting import merge_cleanup_summaries, record_kill_report, snapshot_for_runtime, summary_from_stop_all_payload

__all__ = [
    "await_remote_shutdown",
    "KillPreparation",
    "collect_agent_pid_candidates",
    "collect_candidate_tmux_sockets",
    "coerce_pid",
    "destroy_project_namespace",
    "extra_agent_dir_names",
    "finalize_kill",
    "merge_cleanup_summaries",
    "path_within",
    "pid_matches_project",
    "prepare_local_shutdown",
    "read_pid_file",
    "read_proc_cmdline",
    "read_proc_path",
    "record_kill_report",
    "remove_pid_files",
    "request_remote_stop",
    "resolve_shutdown_summary",
    "snapshot_for_runtime",
    "summary_from_stop_all_payload",
    "terminate_runtime_pids",
]
