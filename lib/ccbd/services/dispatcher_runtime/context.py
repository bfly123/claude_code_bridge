from __future__ import annotations

from agents.models import AgentRuntime
from ccbd.api_models import JobRecord, TargetKind
from provider_execution.base import ProviderRuntimeContext


def _runtime_pid(runtime: AgentRuntime | None) -> int | None:
    if runtime is None:
        return None
    return runtime.runtime_pid if runtime.runtime_pid is not None else runtime.pid


def build_runtime_context(runtime: AgentRuntime | None) -> ProviderRuntimeContext | None:
    if runtime is None:
        return None
    return ProviderRuntimeContext(
        agent_name=runtime.agent_name,
        workspace_path=runtime.workspace_path,
        backend_type=runtime.backend_type,
        runtime_ref=runtime.runtime_ref,
        session_ref=runtime.session_ref,
        runtime_root=runtime.runtime_root,
        runtime_pid=_runtime_pid(runtime),
        runtime_health=runtime.health,
        runtime_binding_source=runtime.binding_source.value,
        terminal_backend=runtime.terminal_backend,
        session_file=runtime.session_file,
        session_id=runtime.session_id,
        tmux_socket_name=runtime.tmux_socket_name,
        tmux_socket_path=runtime.tmux_socket_path,
        job_id=runtime.job_id,
        job_owner_pid=runtime.job_owner_pid,
    )


def build_job_runtime_context(job: JobRecord, runtime: AgentRuntime | None = None) -> ProviderRuntimeContext | None:
    if job.target_kind is TargetKind.AGENT:
        return build_runtime_context(runtime)
    if not job.workspace_path:
        return None
    return ProviderRuntimeContext(
        agent_name=job.agent_name or job.target_name,
        workspace_path=job.workspace_path,
        backend_type='pane-backed',
        runtime_ref=job.target_name,
        session_ref=None,
        runtime_root=runtime.runtime_root if runtime is not None else None,
        runtime_pid=_runtime_pid(runtime),
        runtime_health=runtime.health if runtime is not None else None,
        runtime_binding_source=runtime.binding_source.value if runtime is not None else None,
        terminal_backend=runtime.terminal_backend if runtime is not None else None,
        session_file=runtime.session_file if runtime is not None else None,
        session_id=runtime.session_id if runtime is not None else None,
        tmux_socket_name=runtime.tmux_socket_name if runtime is not None else None,
        tmux_socket_path=runtime.tmux_socket_path if runtime is not None else None,
        job_id=runtime.job_id if runtime is not None else None,
        job_owner_pid=runtime.job_owner_pid if runtime is not None else None,
    )
