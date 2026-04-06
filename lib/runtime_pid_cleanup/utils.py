from __future__ import annotations

from pathlib import Path


def coerce_pid(value: object) -> int | None:
    text = str(value or '').strip()
    if not text.isdigit():
        return None
    pid = int(text)
    return pid if pid > 0 else None


def resolved_runtime_roots(agent_dir: Path, *, runtime, fallback_to_agent_dir: bool) -> list[Path]:
    runtime_root_paths: list[Path] = []
    if runtime is not None:
        runtime_root = getattr(runtime, 'runtime_root', None)
        if isinstance(runtime_root, str) and runtime_root.strip():
            runtime_root_paths.append(Path(runtime_root).expanduser())
    if fallback_to_agent_dir or not runtime_root_paths:
        runtime_root_paths.append(agent_dir / 'provider-runtime')
    resolved: list[Path] = []
    seen: set[Path] = set()
    for root in runtime_root_paths:
        try:
            candidate = root.resolve()
        except Exception:
            candidate = root.absolute()
        if candidate in seen or not candidate.is_dir():
            continue
        seen.add(candidate)
        resolved.append(candidate)
    return resolved


__all__ = ['coerce_pid', 'resolved_runtime_roots']
