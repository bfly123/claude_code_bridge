from __future__ import annotations

import os
from pathlib import Path

from .procfs import read_pid_file, read_proc_cmdline
from .utils import coerce_pid, resolved_runtime_roots


def collect_pid_candidates(agent_dir: Path, *, runtime, fallback_to_agent_dir: bool) -> dict[int, list[Path]]:
    candidates: dict[int, list[Path]] = {}
    if runtime is not None:
        runtime_pid = coerce_pid(getattr(runtime, 'runtime_pid', None) or getattr(runtime, 'pid', None))
        if runtime_pid is not None:
            candidates.setdefault(runtime_pid, []).append(agent_dir / 'runtime.json')
    for root in resolved_runtime_roots(agent_dir, runtime=runtime, fallback_to_agent_dir=fallback_to_agent_dir):
        for pid_path in sorted(root.rglob('*.pid')):
            pid = read_pid_file(pid_path)
            if pid is None:
                continue
            candidates.setdefault(pid, []).append(pid_path)
    return candidates


def runtime_job_owner_pid(agent_dir: Path, *, runtime, fallback_to_agent_dir: bool) -> int | None:
    direct = coerce_pid(getattr(runtime, 'job_owner_pid', None)) if runtime is not None else None
    if direct is not None:
        return direct
    for root in resolved_runtime_roots(agent_dir, runtime=runtime, fallback_to_agent_dir=fallback_to_agent_dir):
        for pid_path in _runtime_marker_paths(root, 'job-owner.pid', 'owner.pid', 'bridge.pid'):
            pid = read_pid_file(pid_path)
            if pid is not None:
                return pid
    return None


def runtime_job_id(agent_dir: Path, *, runtime, fallback_to_agent_dir: bool) -> str | None:
    direct = str(getattr(runtime, 'job_id', '') or '').strip() if runtime is not None else ''
    if direct:
        return direct
    for root in resolved_runtime_roots(agent_dir, runtime=runtime, fallback_to_agent_dir=fallback_to_agent_dir):
        for job_path in _runtime_marker_paths(root, 'job.id'):
            job_id = _read_text_file(job_path)
            if job_id is not None:
                return job_id
    return None


def collect_project_process_candidates(
    project_root: Path,
    *,
    proc_root: Path = Path('/proc'),
    read_proc_cmdline_fn=read_proc_cmdline,
    current_pid: int | None = None,
) -> dict[int, list[Path]]:
    current_pid = int(current_pid or os.getpid())
    ccb_root = project_root.expanduser() / '.ccb'
    marker = str(ccb_root)
    if not marker:
        return {}
    candidates: dict[int, list[Path]] = {}
    try:
        entries = list(proc_root.iterdir())
    except Exception:
        return candidates
    for entry in entries:
        pid = coerce_pid(entry.name)
        if pid is None or pid == current_pid:
            continue
        cmdline = str(read_proc_cmdline_fn(pid) or '').strip()
        if marker not in cmdline:
            continue
        candidates.setdefault(pid, []).append(ccb_root)
    return candidates


def _read_text_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding='utf-8').strip()
    except Exception:
        return None
    return text or None


def _runtime_marker_paths(root: Path, *names: str) -> tuple[Path, ...]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for name in names:
        direct = root / name
        if direct not in seen:
            seen.add(direct)
            candidates.append(direct)
        for nested in sorted(root.rglob(name)):
            if nested in seen:
                continue
            seen.add(nested)
            candidates.append(nested)
    return tuple(candidates)


__all__ = ['collect_pid_candidates', 'collect_project_process_candidates', 'runtime_job_id', 'runtime_job_owner_pid']
