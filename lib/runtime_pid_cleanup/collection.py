from __future__ import annotations

from pathlib import Path

from .procfs import read_pid_file
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


__all__ = ['collect_pid_candidates']
