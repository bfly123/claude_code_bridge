from __future__ import annotations

from cli.kill_runtime.processes import is_pid_alive, terminate_pid_tree
from runtime_pid_cleanup import collect_pid_candidates as _collect_pid_candidates_impl
from runtime_pid_cleanup import collect_project_process_candidates as _collect_project_process_candidates_impl
from runtime_pid_cleanup import LocalProcessTreeOwner
from runtime_pid_cleanup import path_within as _path_within_impl
from runtime_pid_cleanup import pid_matches_project as _pid_matches_project_impl
from runtime_pid_cleanup import ProcessTreeOwnerFactory
from runtime_pid_cleanup import read_proc_cmdline as _read_proc_cmdline_impl
from runtime_pid_cleanup import read_proc_path as _read_proc_path_impl
from runtime_pid_cleanup import remove_pid_files as _remove_pid_files_impl
from runtime_pid_cleanup import runtime_job_id as _runtime_job_id_impl
from runtime_pid_cleanup import runtime_job_owner_pid as _runtime_job_owner_pid_impl
from runtime_pid_cleanup import terminate_runtime_pids as _terminate_runtime_pids_impl
from runtime_pid_cleanup import WindowsJobMetadataProcessTreeOwnerFactory


def collect_pid_candidates(agent_dir, *, runtime, fallback_to_agent_dir: bool):
    return _collect_pid_candidates_impl(agent_dir, runtime=runtime, fallback_to_agent_dir=fallback_to_agent_dir)


def runtime_job_owner_pid(agent_dir, *, runtime, fallback_to_agent_dir: bool):
    return _runtime_job_owner_pid_impl(agent_dir, runtime=runtime, fallback_to_agent_dir=fallback_to_agent_dir)


def runtime_job_id(agent_dir, *, runtime, fallback_to_agent_dir: bool):
    return _runtime_job_id_impl(agent_dir, runtime=runtime, fallback_to_agent_dir=fallback_to_agent_dir)


def terminate_runtime_pids(*, project_root, pid_candidates, priority_pids=(), pid_metadata=None, process_tree_owner_factory: ProcessTreeOwnerFactory | None = None) -> None:
    local_owner = LocalProcessTreeOwner(terminate_pid_tree)
    _terminate_runtime_pids_impl(
        project_root=project_root,
        pid_candidates=pid_candidates,
        priority_pids=priority_pids,
        pid_metadata=pid_metadata,
        is_pid_alive_fn=is_pid_alive,
        pid_matches_project_fn=pid_matches_project,
        process_tree_owner=local_owner,
        process_tree_owner_factory=process_tree_owner_factory or WindowsJobMetadataProcessTreeOwnerFactory(local_owner),
        remove_pid_files_fn=remove_pid_files,
        collect_project_process_candidates_fn=collect_project_process_candidates,
    )


def pid_matches_project(pid: int, *, project_root, hint_paths) -> bool:
    return _pid_matches_project_impl(
        pid,
        project_root=project_root,
        hint_paths=hint_paths,
        read_proc_path_fn=read_proc_path,
        read_proc_cmdline_fn=read_proc_cmdline,
        path_within_fn=path_within,
    )


def read_proc_path(pid: int, entry: str):
    return _read_proc_path_impl(pid, entry)


def read_proc_cmdline(pid: int) -> str:
    return _read_proc_cmdline_impl(pid)


def path_within(path, root) -> bool:
    return _path_within_impl(path, root)


def remove_pid_files(paths) -> None:
    _remove_pid_files_impl(paths)


def collect_project_process_candidates(project_root, **kwargs):
    return _collect_project_process_candidates_impl(project_root, **kwargs)


__all__ = ['collect_pid_candidates', 'collect_project_process_candidates', 'runtime_job_id', 'runtime_job_owner_pid', 'terminate_runtime_pids']
