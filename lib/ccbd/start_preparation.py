from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents.policy import resolve_agent_launch_policy
from agents.store import AgentRestoreStore, AgentSpecStore
from cli.services.provider_hooks import prepare_workspace_provider_hooks
from provider_profiles import materialize_provider_profile
from workspace.binding import WorkspaceBindingStore
from workspace.materializer import WorkspaceMaterializer
from workspace.planner import WorkspacePlanner
from workspace.validator import WorkspaceValidator


@dataclass(frozen=True)
class PreparedStartAgent:
    agent_name: str
    spec: object
    plan: object
    raw_binding: object | None
    binding: object | None
    stale_binding: bool


def prepare_start_agents(
    *,
    targets: tuple[str, ...],
    config,
    paths,
    context,
    project_root: Path,
    project_id: str,
    tmux_socket_path: str | None,
    tmux_session_name: str | None,
    resolve_agent_binding_fn,
    project_binding_filter_fn,
    restore_state_builder,
) -> tuple[PreparedStartAgent, ...]:
    spec_store = AgentSpecStore(paths)
    restore_store = AgentRestoreStore(paths)
    planner = WorkspacePlanner()
    binding_store = WorkspaceBindingStore()
    materializer = WorkspaceMaterializer()
    validator = WorkspaceValidator(binding_store)
    prepared: list[PreparedStartAgent] = []

    for agent_name in targets:
        spec = config.agents[agent_name]
        spec_store.save(spec)
        policy = resolve_agent_launch_policy(
            spec,
            cli_restore=context.command.restore,
            cli_auto_permission=context.command.auto_permission,
        )
        plan = planner.plan(spec, context.project)
        materializer.materialize(plan)
        if plan.binding_path is not None:
            binding_store.save(plan)
        prepare_workspace_provider_hooks(
            provider=spec.provider,
            workspace_path=plan.workspace_path,
            completion_dir=paths.agent_provider_runtime_dir(agent_name, spec.provider) / 'completion',
            agent_name=agent_name,
            resolved_profile=materialize_provider_profile(
                layout=paths,
                spec=spec,
                workspace_path=plan.workspace_path,
            ),
        )
        result = validator.validate(plan)
        if not result.ok:
            raise RuntimeError(f'workspace validation failed for {agent_name}: {result.errors}')

        raw_binding = resolve_agent_binding_fn(
            provider=spec.provider,
            agent_name=agent_name,
            workspace_path=plan.workspace_path,
            project_root=project_root,
            ensure_usable=False,
        )
        if tmux_socket_path is not None:
            binding = project_binding_filter_fn(
                raw_binding,
                cmd_enabled=bool(getattr(config, 'cmd_enabled', False)),
                tmux_socket_path=tmux_socket_path,
                tmux_session_name=tmux_session_name,
                agent_name=agent_name,
                project_id=project_id,
            )
        else:
            binding = resolve_agent_binding_fn(
                provider=spec.provider,
                agent_name=agent_name,
                workspace_path=plan.workspace_path,
                project_root=project_root,
                ensure_usable=True,
            )

        if restore_store.load(agent_name) is None:
            restore_store.save(agent_name, restore_state_builder(policy.restore_mode.value))

        prepared.append(
            PreparedStartAgent(
                agent_name=agent_name,
                spec=spec,
                plan=plan,
                raw_binding=raw_binding,
                binding=binding,
                stale_binding=raw_binding is not None and binding is None,
            )
        )

    return tuple(prepared)


__all__ = ['PreparedStartAgent', 'prepare_start_agents']
