from __future__ import annotations

from agents.config_loader import load_project_config
from agents.store import AgentRuntimeStore
from cli.context import CliContext
from cli.models import ParsedPsCommand

from .daemon import ping_local_state
from .provider_binding import binding_status


def ps_summary(context: CliContext, command: ParsedPsCommand) -> dict:
    del command
    config = load_project_config(context.project.project_root).config
    store = AgentRuntimeStore(context.paths)
    local = ping_local_state(context)
    agents: list[dict] = []
    for agent_name, spec in sorted(config.agents.items()):
        runtime = store.load(agent_name)
        agents.append(_agent_summary(context, agent_name=agent_name, spec=spec, runtime=runtime))
    return {
        'project_id': context.project.project_id,
        'ccbd_state': local.mount_state,
        'agents': agents,
    }


def _agent_summary(context: CliContext, *, agent_name: str, spec, runtime) -> dict:
    workspace_path = _workspace_path(context, agent_name=agent_name, runtime=runtime)
    runtime_ref = _runtime_attr(runtime, 'runtime_ref')
    session_ref = _session_ref(runtime)
    return {
        'agent_name': agent_name,
        'provider': spec.provider,
        'runtime_mode': spec.runtime_mode.value,
        'workspace_mode': spec.workspace_mode.value,
        'state': _runtime_enum_value(runtime, 'state', 'stopped'),
        'queue_depth': _runtime_attr(runtime, 'queue_depth', 0),
        'workspace_path': workspace_path,
        'runtime_ref': runtime_ref,
        'session_ref': session_ref,
        'binding_status': binding_status(runtime_ref, session_ref, workspace_path),
        'backend_type': _runtime_attr(runtime, 'backend_type', spec.runtime_mode.value),
        'binding_source': _runtime_enum_value(runtime, 'binding_source', 'provider-session'),
        'terminal': _runtime_attr(runtime, 'terminal_backend'),
        'runtime_pid': _runtime_attr(runtime, 'runtime_pid'),
        'runtime_root': _runtime_attr(runtime, 'runtime_root'),
        'session_file': _runtime_attr(runtime, 'session_file'),
        'session_id': _runtime_attr(runtime, 'session_id'),
        'job_id': _runtime_attr(runtime, 'job_id'),
        'job_owner_pid': _runtime_attr(runtime, 'job_owner_pid'),
        'tmux_socket_name': _runtime_attr(runtime, 'tmux_socket_name'),
        'tmux_socket_path': _runtime_attr(runtime, 'tmux_socket_path'),
        'pane_id': _runtime_attr(runtime, 'pane_id'),
        'active_pane_id': _runtime_attr(runtime, 'active_pane_id'),
        'pane_title_marker': _runtime_attr(runtime, 'pane_title_marker'),
        'pane_state': _runtime_attr(runtime, 'pane_state'),
    }


def _runtime_attr(runtime, name: str, default=None):
    if runtime is None:
        return default
    return getattr(runtime, name, default)


def _runtime_enum_value(runtime, name: str, default: str) -> str:
    value = _runtime_attr(runtime, name)
    return getattr(value, 'value', default)


def _workspace_path(context: CliContext, *, agent_name: str, runtime) -> str:
    workspace_path = _runtime_attr(runtime, 'workspace_path')
    if workspace_path:
        return runtime.workspace_path
    return str(context.paths.workspace_path(agent_name))


def _session_ref(runtime) -> str | None:
    if runtime is None:
        return None
    return runtime.session_file or runtime.session_id or runtime.session_ref
