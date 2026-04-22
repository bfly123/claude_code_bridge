from __future__ import annotations

import os
from pathlib import Path

from provider_runtime.helper_manifest import load_helper_manifest

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
    helper_path = agent_dir / 'helper.json'
    helper = _load_helper_manifest_best_effort(helper_path)
    if helper is not None:
        candidates.setdefault(helper.leader_pid, []).append(helper_path)
    return candidates


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


__all__ = ['collect_pid_candidates', 'collect_project_process_candidates']


def _load_helper_manifest_best_effort(path: Path):
    try:
        return load_helper_manifest(path)
    except Exception:
        return None
