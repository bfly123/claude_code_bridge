from __future__ import annotations


def terminate_runtime_pids(
    *,
    project_root,
    pid_candidates,
    is_pid_alive_fn,
    pid_matches_project_fn,
    terminate_pid_tree_fn,
    remove_pid_files_fn,
) -> None:
    for pid in sorted(pid_candidates):
        hint_paths = tuple(dict.fromkeys(pid_candidates[pid]))
        if not is_pid_alive_fn(pid):
            remove_pid_files_fn(hint_paths)
            continue
        if not pid_matches_project_fn(pid, project_root=project_root, hint_paths=hint_paths):
            continue
        if terminate_pid_tree_fn(pid, timeout_s=1.0, is_pid_alive_fn=is_pid_alive_fn):
            remove_pid_files_fn(hint_paths)


__all__ = ['terminate_runtime_pids']
