from __future__ import annotations

from agents.models import AgentRuntime
from ccbd.api_models import JobRecord, TargetKind
from provider_execution.base import ProviderRuntimeContext


def build_runtime_context(runtime: AgentRuntime | None) -> ProviderRuntimeContext | None:
    if runtime is None:
        return None
    return ProviderRuntimeContext(
        agent_name=runtime.agent_name,
        workspace_path=runtime.workspace_path,
        backend_type=runtime.backend_type,
        runtime_ref=runtime.runtime_ref,
        session_ref=runtime.session_ref,
        runtime_pid=runtime.pid,
        runtime_health=runtime.health,
        runtime_binding_source=runtime.binding_source.value,
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
        runtime_pid=runtime.pid if runtime is not None else None,
        runtime_health=runtime.health if runtime is not None else None,
        runtime_binding_source=runtime.binding_source.value if runtime is not None else None,
    )
