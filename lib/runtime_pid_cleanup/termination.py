from __future__ import annotations

from .process_tree_owner import ProcessTreeTarget


def terminate_runtime_pids(
    *,
    project_root,
    pid_candidates,
    priority_pids=(),
    pid_metadata=None,
    is_pid_alive_fn,
    pid_matches_project_fn,
    terminate_pid_tree_fn=None,
    process_tree_owner=None,
    process_tree_owner_factory=None,
    remove_pid_files_fn,
    collect_project_process_candidates_fn=None,
) -> None:
    merged_candidates: dict[int, list] = {pid: list(paths) for pid, paths in pid_candidates.items()}
    terminated_job_ids: set[str] = set()
    if collect_project_process_candidates_fn is not None:
        for pid, sources in collect_project_process_candidates_fn(project_root).items():
            merged_candidates.setdefault(pid, []).extend(sources)
    for pid in _ordered_pids(merged_candidates, priority_pids=priority_pids):
        hint_paths = tuple(dict.fromkeys(merged_candidates[pid]))
        metadata = _pid_metadata(pid_metadata, pid)
        job_id = _job_id(metadata)
        if job_id is not None and job_id in terminated_job_ids:
            remove_pid_files_fn(hint_paths)
            continue
        if not is_pid_alive_fn(pid):
            remove_pid_files_fn(hint_paths)
            continue
        if not pid_matches_project_fn(pid, project_root=project_root, hint_paths=hint_paths):
            continue
        owner = _process_tree_owner_for_pid(
            pid,
            hint_paths=hint_paths,
            pid_metadata=pid_metadata,
            process_tree_owner=process_tree_owner,
            process_tree_owner_factory=process_tree_owner_factory,
        )
        if _terminate_pid(
            pid,
            timeout_s=1.0,
            is_pid_alive_fn=is_pid_alive_fn,
            terminate_pid_tree_fn=terminate_pid_tree_fn,
            process_tree_owner=owner,
        ):
            if job_id is not None and _job_owner_pid(metadata) == pid:
                terminated_job_ids.add(job_id)
            remove_pid_files_fn(hint_paths)


def _ordered_pids(merged_candidates: dict[int, list], *, priority_pids) -> tuple[int, ...]:
    ordered: list[int] = []
    seen: set[int] = set()
    for pid in priority_pids:
        if pid in merged_candidates and pid not in seen:
            ordered.append(pid)
            seen.add(pid)
    for pid in sorted(merged_candidates):
        if pid in seen:
            continue
        ordered.append(pid)
        seen.add(pid)
    return tuple(ordered)


def _terminate_pid(
    pid: int,
    *,
    timeout_s: float,
    is_pid_alive_fn,
    terminate_pid_tree_fn,
    process_tree_owner,
) -> bool:
    if process_tree_owner is not None:
        return process_tree_owner.terminate(pid, timeout_s=timeout_s, is_pid_alive_fn=is_pid_alive_fn)
    if terminate_pid_tree_fn is None:
        raise ValueError('terminate_pid_tree_fn or process_tree_owner is required')
    return terminate_pid_tree_fn(pid, timeout_s=timeout_s, is_pid_alive_fn=is_pid_alive_fn)


def _process_tree_owner_for_pid(
    pid: int,
    *,
    hint_paths,
    pid_metadata,
    process_tree_owner,
    process_tree_owner_factory,
):
    if process_tree_owner_factory is None:
        return process_tree_owner
    metadata = None
    if isinstance(pid_metadata, dict):
        raw = pid_metadata.get(pid)
        if isinstance(raw, dict):
            metadata = dict(raw)
    selected = process_tree_owner_factory.build(
        ProcessTreeTarget(
            pid=pid,
            hint_paths=hint_paths,
            metadata=metadata,
        )
    )
    if selected is not None:
        return selected
    return process_tree_owner


def _pid_metadata(pid_metadata, pid: int) -> dict[str, object] | None:
    if not isinstance(pid_metadata, dict):
        return None
    raw = pid_metadata.get(pid)
    if not isinstance(raw, dict):
        return None
    return dict(raw)


def _job_id(metadata: dict[str, object] | None) -> str | None:
    text = str((metadata or {}).get('job_id') or '').strip()
    return text or None


def _job_owner_pid(metadata: dict[str, object] | None) -> int | None:
    text = str((metadata or {}).get('job_owner_pid') or '').strip()
    if not text.isdigit():
        return None
    pid = int(text)
    return pid if pid > 0 else None


__all__ = ['terminate_runtime_pids']
