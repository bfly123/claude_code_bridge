from __future__ import annotations

from agents.config_loader import load_project_config
from agents.store import AgentRuntimeStore
from cli.context import CliContext
from cli.models import ParsedPsCommand

from .daemon import ping_local_state
from .provider_binding import binding_status


def ps_summary(context: CliContext, command: ParsedPsCommand) -> dict:
    config = load_project_config(context.project.project_root).config
    store = AgentRuntimeStore(context.paths)
    local = ping_local_state(context)
    agents: list[dict] = []
    for agent_name, spec in sorted(config.agents.items()):
        runtime = store.load(agent_name)
        if command.alive_only and runtime is None:
            continue
        if command.alive_only and runtime is not None and runtime.state.value not in {'starting', 'idle', 'busy', 'degraded'}:
            continue
        workspace_path = runtime.workspace_path if runtime is not None and runtime.workspace_path else str(context.paths.workspace_path(agent_name))
        runtime_ref = runtime.runtime_ref if runtime is not None else None
        session_ref = None
        if runtime is not None:
            session_ref = runtime.session_file or runtime.session_id or runtime.session_ref
        agents.append(
            {
                'agent_name': agent_name,
                'provider': spec.provider,
                'runtime_mode': spec.runtime_mode.value,
                'workspace_mode': spec.workspace_mode.value,
                'state': runtime.state.value if runtime is not None else 'stopped',
                'queue_depth': runtime.queue_depth if runtime is not None else 0,
                'workspace_path': workspace_path,
                'runtime_ref': runtime_ref,
                'session_ref': session_ref,
                'binding_status': binding_status(runtime_ref, session_ref, workspace_path),
                'backend_type': runtime.backend_type if runtime is not None else spec.runtime_mode.value,
                'binding_source': runtime.binding_source.value if runtime is not None else 'provider-session',
                'terminal': runtime.terminal_backend if runtime is not None else None,
                'tmux_socket_name': runtime.tmux_socket_name if runtime is not None else None,
                'tmux_socket_path': runtime.tmux_socket_path if runtime is not None else None,
                'pane_id': runtime.pane_id if runtime is not None else None,
                'active_pane_id': runtime.active_pane_id if runtime is not None else None,
                'pane_title_marker': runtime.pane_title_marker if runtime is not None else None,
                'pane_state': runtime.pane_state if runtime is not None else None,
            }
        )
    return {'project_id': context.project.project_id, 'ccbd_state': local.mount_state, 'agents': agents}
