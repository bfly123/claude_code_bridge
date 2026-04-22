from __future__ import annotations

from dataclasses import dataclass

from agents.models import AgentState
from agents.models import build_project_layout_plan
from ccbd.services.project_namespace import ProjectNamespaceController
from ccbd.services.project_namespace_pane import inspect_project_namespace_pane
from ccbd.services.project_namespace_runtime.backend import build_backend
from ccbd.start_runtime.layout import cmd_bootstrap_command
from terminal_runtime.tmux_identity import apply_ccb_pane_identity

from .loop_context import RuntimeSupervisionContext

_PLACEHOLDER_CMD = 'while :; do sleep 3600; done'


@dataclass(frozen=True)
class CmdLocalReplacementPlan:
    tmux_direction_flag: str
    percent: int


def reconcile_cmd_slot(ctx: RuntimeSupervisionContext) -> str | None:
    if not bool(getattr(ctx.config, 'cmd_enabled', False)):
        return None
    namespace_controller = ProjectNamespaceController(ctx.layout, ctx.project_id)
    namespace = _load_namespace(namespace_controller)
    if namespace is None or not bool(getattr(namespace, 'ui_attachable', False)):
        return 'namespace-unavailable'
    backend = _build_namespace_backend(namespace_controller, namespace)
    if backend is None:
        return request_cmd_workspace_reflow(ctx)
    root_pane_id = _load_root_pane_id(namespace_controller, namespace)
    record = _inspect_root_record(backend, root_pane_id)
    if cmd_slot_matches_namespace(ctx, namespace, record):
        return 'healthy'
    if replace_cmd_slot_locally(
        ctx,
        backend=backend,
        namespace=namespace,
        anchor_pane_id=root_pane_id,
    ):
        return 'restored-local'
    return request_cmd_workspace_reflow(ctx)


def request_cmd_workspace_reflow(ctx: RuntimeSupervisionContext) -> str:
    if ctx.remount_project_fn is None:
        return 'unhealthy'
    if other_project_agent_busy(ctx):
        return 'blocked-busy'
    ctx.remount_project_fn('pane_recovery:cmd')
    return 'recovering'


def replace_cmd_slot_locally(
    ctx: RuntimeSupervisionContext,
    *,
    backend,
    namespace,
    anchor_pane_id: str | None,
) -> bool:
    pane_text = str(anchor_pane_id or '').strip()
    if not pane_text.startswith('%'):
        return False
    plan = resolve_cmd_local_replacement_plan(ctx)
    if plan is None:
        return False
    new_pane_id = split_before_anchor_pane(
        backend,
        anchor_pane_id=pane_text,
        project_root=str(ctx.layout.project_root),
        plan=plan,
    )
    if new_pane_id is None:
        return False
    respawn = getattr(backend, 'respawn_pane', None)
    if not callable(respawn):
        return False
    respawn(
        new_pane_id,
        cmd=cmd_bootstrap_command(),
        cwd=str(ctx.layout.project_root),
        remain_on_exit=False,
    )
    apply_ccb_pane_identity(
        backend,
        new_pane_id,
        title='cmd',
        agent_label='cmd',
        project_id=ctx.project_id,
        is_cmd=True,
        slot_key='cmd',
        namespace_epoch=getattr(namespace, 'namespace_epoch', None),
        managed_by='ccbd',
    )
    record = _inspect_root_record(backend, new_pane_id)
    return cmd_slot_matches_namespace(ctx, namespace, record)


def resolve_cmd_local_replacement_plan(ctx: RuntimeSupervisionContext) -> CmdLocalReplacementPlan | None:
    try:
        layout = build_project_layout_plan(
            ctx.config,
            target_agent_names=tuple(getattr(ctx.config, 'agents', ())),
        ).layout
    except Exception:
        return None
    parent = find_cmd_leaf_parent(layout)
    if parent is None or parent.right is None:
        return None
    total = max(1, int(parent.leaf_count))
    left_percent = max(1, min(99, round(100 / total)))
    return CmdLocalReplacementPlan(
        tmux_direction_flag='-h' if parent.kind == 'horizontal' else '-v',
        percent=left_percent,
    )


def find_cmd_leaf_parent(node):
    current = node
    while current is not None and getattr(current, 'kind', None) != 'leaf':
        left = getattr(current, 'left', None)
        if left is not None and getattr(left, 'kind', None) == 'leaf':
            leaf = getattr(left, 'leaf', None)
            if str(getattr(leaf, 'name', '') or '').strip() == 'cmd':
                return current
        current = left
    return None


def split_before_anchor_pane(
    backend,
    *,
    anchor_pane_id: str,
    project_root: str,
    plan: CmdLocalReplacementPlan,
) -> str | None:
    runner = getattr(backend, '_tmux_run', None)
    if not callable(runner):
        return None
    try:
        cp = runner(
            [
                'split-pane',
                '-P',
                '-F',
                '#{pane_id}',
                '-t',
                anchor_pane_id,
                plan.tmux_direction_flag,
                '-b',
                '-p',
                str(plan.percent),
                '-c',
                project_root,
                'sh',
                '-lc',
                _PLACEHOLDER_CMD,
            ],
            capture=True,
            check=True,
        )
    except Exception:
        return None
    pane_id = ((getattr(cp, 'stdout', '') or '').splitlines() or [''])[0].strip()
    return pane_id if pane_id.startswith('%') else None


def cmd_slot_matches_namespace(
    ctx: RuntimeSupervisionContext,
    namespace,
    record,
) -> bool:
    if record is None:
        return False
    workspace_window_id = str(getattr(namespace, 'workspace_window_id', None) or '').strip() or None
    return record.matches(
        tmux_session_name=_namespace_session_name(namespace),
        project_id=ctx.project_id,
        role='cmd',
        slot_key='cmd',
        managed_by='ccbd',
        window_id=workspace_window_id,
    )


def other_project_agent_busy(ctx: RuntimeSupervisionContext) -> bool:
    for agent_name in tuple(getattr(ctx.config, 'agents', ()) or ()):
        runtime = ctx.registry.get(agent_name)
        if runtime is None:
            continue
        if runtime.state is AgentState.BUSY:
            return True
    return False


def _load_namespace(namespace_controller: ProjectNamespaceController):
    try:
        return namespace_controller.load()
    except Exception:
        return None


def _build_namespace_backend(namespace_controller: ProjectNamespaceController, namespace):
    try:
        return build_backend(
            namespace_controller._backend_factory,
            socket_path=_namespace_backend_ref(namespace),
        )
    except Exception:
        return None


def _inspect_root_record(backend, pane_id: str | None):
    pane_text = str(pane_id or '').strip()
    if not pane_text.startswith('%'):
        return None
    try:
        return inspect_project_namespace_pane(backend, pane_text)
    except Exception:
        return None


def _load_root_pane_id(namespace_controller: ProjectNamespaceController, namespace) -> str | None:
    try:
        pane_id = namespace_controller.root_pane_id(namespace)
    except Exception:
        return None
    pane_text = str(pane_id or '').strip()
    return pane_text if pane_text.startswith('%') else None


def _namespace_backend_ref(namespace) -> str:
    return str(getattr(namespace, 'backend_ref', None) or getattr(namespace, 'tmux_socket_path', None) or '').strip()


def _namespace_session_name(namespace) -> str:
    return str(getattr(namespace, 'session_name', None) or getattr(namespace, 'tmux_session_name', None) or '').strip()


__all__ = ['reconcile_cmd_slot']
