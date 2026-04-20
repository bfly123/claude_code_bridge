from __future__ import annotations

from runtime_pid_cleanup import collect_pid_candidates as _collect_pid_candidates_impl
from runtime_pid_cleanup import collect_project_process_candidates
from runtime_pid_cleanup import coerce_pid
from runtime_pid_cleanup import path_within
from runtime_pid_cleanup import pid_matches_project
from runtime_pid_cleanup import read_pid_file, read_proc_cmdline, read_proc_path, remove_pid_files
from runtime_pid_cleanup import terminate_runtime_pids


def collect_agent_pid_candidates(agent_dir, *, runtime, fallback_to_agent_dir: bool):
    return _collect_pid_candidates_impl(agent_dir, runtime=runtime, fallback_to_agent_dir=fallback_to_agent_dir)


__all__ = [
    "collect_agent_pid_candidates",
    "collect_project_process_candidates",
    "coerce_pid",
    "path_within",
    "pid_matches_project",
    "read_pid_file",
    "read_proc_cmdline",
    "read_proc_path",
    "remove_pid_files",
    "terminate_runtime_pids",
]
