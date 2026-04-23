from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path

from agents.config_loader import load_project_config
from agents.models import AgentState
from agents.store import AgentRuntimeStore
from terminal_runtime.tmux import normalize_socket_name, socket_name_from_tmux_env

from .pid_cleanup import runtime_job_id, runtime_job_owner_pid


@dataclass(frozen=True)
class KillPreparation:
    configured_agent_names: tuple[str, ...]
    extra_agent_names: tuple[str, ...]
    tmux_sockets: tuple[str | None, ...]
    priority_pids: tuple[int, ...]
    pid_metadata: dict[int, dict[str, object]]
    pid_candidates: dict[int, list[Path]]


def prepare_local_shutdown(context, *, force: bool, collect_agent_pid_candidates_fn) -> KillPreparation:
    store = AgentRuntimeStore(context.paths)
    configured_agent_names = _configured_agent_names(context)
    tmux_sockets = collect_candidate_tmux_sockets() if configured_agent_names else set()
    extra_agent_names = extra_agent_dir_names(context, configured_agent_names)
    pid_candidates: dict[int, list[Path]] = {}
    priority_pids: list[int] = []
    pid_metadata: dict[int, dict[str, object]] = {}
    for agent_name in (*configured_agent_names, *extra_agent_names):
        runtime = store.load_best_effort(agent_name)
        _capture_runtime_tmux_socket(tmux_sockets, runtime)
        agent_dir = context.paths.agent_dir(agent_name)
        owner_pid = _runtime_job_owner_pid(agent_dir, runtime, fallback_to_agent_dir=force)
        job_id = _runtime_job_id(agent_dir, runtime, fallback_to_agent_dir=force)
        if owner_pid is not None and owner_pid not in priority_pids:
            priority_pids.append(owner_pid)
        for pid, sources in collect_agent_pid_candidates_fn(
            agent_dir=agent_dir,
            runtime=runtime,
            fallback_to_agent_dir=force,
        ).items():
            pid_candidates.setdefault(pid, []).extend(sources)
            _capture_pid_metadata(pid_metadata, pid, job_id=job_id, job_owner_pid=owner_pid)
            if owner_pid is not None and owner_pid != pid:
                pid_candidates.setdefault(owner_pid, []).extend(sources)
                _capture_pid_metadata(pid_metadata, owner_pid, job_id=job_id, job_owner_pid=owner_pid)
        if runtime is None:
            continue
        store.save(_stopped_runtime(runtime))
    return KillPreparation(
        configured_agent_names=configured_agent_names,
        extra_agent_names=extra_agent_names,
        tmux_sockets=tuple(tmux_sockets),
        priority_pids=tuple(priority_pids),
        pid_metadata=pid_metadata,
        pid_candidates=pid_candidates,
    )


def collect_candidate_tmux_sockets() -> set[str | None]:
    sockets: set[str | None] = set()
    for value in (
        normalize_socket_name(os.environ.get("CCB_TMUX_SOCKET")),
        socket_name_from_tmux_env(os.environ.get("TMUX")),
    ):
        if value is not None:
            sockets.add(value)
    return sockets or {None}


def extra_agent_dir_names(context, configured_agent_names: tuple[str, ...]) -> tuple[str, ...]:
    names: list[str] = []
    known = set(configured_agent_names)
    agents_dir = context.paths.agents_dir
    if agents_dir.is_dir():
        for child in sorted(agents_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name in known or child.name in names:
                continue
            names.append(child.name)
    return tuple(names)


def _configured_agent_names(context) -> tuple[str, ...]:
    try:
        return tuple(load_project_config(context.project.project_root).config.agents)
    except Exception:
        return ()


def _capture_runtime_tmux_socket(tmux_sockets: set[str | None], runtime) -> None:
    if runtime is None:
        return
    if not str(runtime.runtime_ref or "").startswith("tmux:"):
        return
    if getattr(runtime, "tmux_socket_path", None) is not None:
        return
    socket_name = normalize_socket_name(runtime.tmux_socket_name)
    if socket_name is not None:
        tmux_sockets.add(socket_name)


def _runtime_job_owner_pid(agent_dir: Path, runtime, *, fallback_to_agent_dir: bool) -> int | None:
    return runtime_job_owner_pid(agent_dir, runtime=runtime, fallback_to_agent_dir=fallback_to_agent_dir)


def _runtime_job_id(agent_dir: Path, runtime, *, fallback_to_agent_dir: bool) -> str | None:
    return runtime_job_id(agent_dir, runtime=runtime, fallback_to_agent_dir=fallback_to_agent_dir)


def _capture_pid_metadata(
    pid_metadata: dict[int, dict[str, object]],
    pid: int | None,
    *,
    job_id: str | None,
    job_owner_pid: int | None,
) -> None:
    if pid is None:
        return
    entry = pid_metadata.setdefault(pid, {})
    normalized_job_id = str(job_id or '').strip()
    if normalized_job_id and 'job_id' not in entry:
        entry['job_id'] = normalized_job_id
    if job_owner_pid is not None and 'job_owner_pid' not in entry:
        entry['job_owner_pid'] = job_owner_pid


def _stopped_runtime(runtime):
    return replace(
        runtime,
        state=AgentState.STOPPED,
        pid=None,
        runtime_ref=None,
        session_ref=None,
        queue_depth=0,
        socket_path=None,
        health="stopped",
        runtime_pid=None,
        job_id=None,
        job_owner_pid=None,
        runtime_root=None,
        pane_id=None,
        active_pane_id=None,
        pane_title_marker=None,
        pane_state=None,
        tmux_socket_name=None,
        tmux_socket_path=None,
        session_file=None,
        session_id=None,
        lifecycle_state="stopped",
        desired_state="stopped",
        reconcile_state="stopped",
        last_failure_reason=None,
    )


__all__ = [
    "KillPreparation",
    "collect_candidate_tmux_sockets",
    "extra_agent_dir_names",
    "prepare_local_shutdown",
]
