from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path

from agents.models import build_project_layout_plan
from agents.policy import resolve_agent_launch_policy
from agents.store import AgentRestoreStore, AgentSpecStore
from ccbd.models import CcbdStartupAgentResult
from ccbd.system import utc_now
from ccbd.services.project_namespace_pane import inspect_project_namespace_pane, same_tmux_socket_path
from cli.context import CliContext
from cli.models import ParsedStartCommand
from cli.services.provider_binding import resolve_agent_binding
from cli.services.provider_hooks import prepare_workspace_provider_hooks
from cli.services.runtime_launch import ensure_agent_runtime
from cli.services.tmux_cleanup_history import TmuxCleanupEvent, TmuxCleanupHistoryStore
from cli.services.tmux_project_cleanup import ProjectTmuxCleanupSummary, cleanup_project_tmux_orphans_by_socket
from cli.services.tmux_start_layout import TmuxStartLayout, prepare_tmux_start_layout
from cli.services.tmux_ui import set_tmux_ui_active
from project.resolver import ProjectContext
from provider_profiles import materialize_provider_profile
from terminal_runtime import TmuxBackend
from terminal_runtime.tmux_identity import apply_ccb_pane_identity
from workspace.binding import WorkspaceBindingStore
from workspace.materializer import WorkspaceMaterializer
from workspace.planner import WorkspacePlanner
from workspace.validator import WorkspaceValidator


@dataclass(frozen=True)
class StartFlowSummary:
    project_root: str
    project_id: str
    started: tuple[str, ...]
    socket_path: str
    cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...] = ()
    actions_taken: tuple[str, ...] = ()
    agent_results: tuple[CcbdStartupAgentResult, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            'project_root': self.project_root,
            'project_id': self.project_id,
            'started': list(self.started),
            'socket_path': self.socket_path,
            'actions_taken': list(self.actions_taken),
            'cleanup_summaries': [
                {
                    'socket_name': item.socket_name,
                    'owned_panes': list(item.owned_panes),
                    'active_panes': list(item.active_panes),
                    'orphaned_panes': list(item.orphaned_panes),
                    'killed_panes': list(item.killed_panes),
                }
                for item in self.cleanup_summaries
            ],
            'agent_results': [item.to_record() for item in self.agent_results],
        }


def run_start_flow(
    *,
    project_root: Path,
    project_id: str,
    paths,
    config,
    runtime_service,
    requested_agents: tuple[str, ...],
    restore: bool,
    auto_permission: bool,
    cleanup_tmux_orphans: bool = True,
    interactive_tmux_layout: bool = True,
    tmux_socket_path: str | None = None,
    tmux_session_name: str | None = None,
    namespace_epoch: int | None = None,
    fresh_namespace: bool = False,
    clock=utc_now,
) -> StartFlowSummary:
    command = ParsedStartCommand(
        project=str(project_root),
        agent_names=tuple(requested_agents),
        restore=bool(restore),
        auto_permission=bool(auto_permission),
    )
    context = CliContext(
        command=command,
        cwd=project_root,
        project=ProjectContext(
            cwd=project_root,
            project_root=project_root,
            config_dir=paths.ccb_dir,
            project_id=project_id,
            source='ccbd',
        ),
        paths=paths,
    )
    layout_plan = build_project_layout_plan(config, requested_agents=command.agent_names)
    targets = layout_plan.target_agent_names
    spec_store = AgentSpecStore(paths)
    restore_store = AgentRestoreStore(paths)
    planner = WorkspacePlanner()
    binding_store = WorkspaceBindingStore()
    materializer = WorkspaceMaterializer()
    validator = WorkspaceValidator(binding_store)
    plans_by_agent = {}
    bindings_by_agent = {}
    raw_bindings_by_agent = {}
    stale_binding_by_agent: dict[str, bool] = {}
    actions_taken: list[str] = []
    agent_results: list[CcbdStartupAgentResult] = []
    tmux_backend = TmuxBackend(socket_path=tmux_socket_path) if tmux_socket_path is not None else None
    root_pane_id = _session_root_pane(tmux_backend, tmux_session_name) if tmux_backend is not None and tmux_session_name else None

    if tmux_socket_path is not None and tmux_session_name is not None:
        actions_taken.append(
            'ensure_namespace:'
            f'epoch={namespace_epoch if namespace_epoch is not None else "unknown"},'
            f'session={tmux_session_name}'
        )

    for agent_name in targets:
        spec = config.agents[agent_name]
        spec_store.save(spec)
        policy = resolve_agent_launch_policy(spec, cli_restore=command.restore, cli_auto_permission=command.auto_permission)
        plan = planner.plan(spec, context.project)
        plans_by_agent[agent_name] = plan
        materializer.materialize(plan)
        resolved_profile = materialize_provider_profile(
            layout=paths,
            spec=spec,
            workspace_path=plan.workspace_path,
        )
        if plan.binding_path is not None:
            binding_store.save(plan)
        prepare_workspace_provider_hooks(
            provider=spec.provider,
            workspace_path=plan.workspace_path,
            completion_dir=paths.agent_provider_runtime_dir(agent_name, spec.provider) / 'completion',
            agent_name=agent_name,
            resolved_profile=resolved_profile,
        )
        result = validator.validate(plan)
        if not result.ok:
            raise RuntimeError(f'workspace validation failed for {agent_name}: {result.errors}')
        raw_binding = resolve_agent_binding(
            provider=spec.provider,
            agent_name=agent_name,
            workspace_path=plan.workspace_path,
            project_root=project_root,
            ensure_usable=False,
        )
        raw_bindings_by_agent[agent_name] = raw_binding
        if tmux_socket_path is not None:
            bindings_by_agent[agent_name] = _usable_project_binding(
                raw_binding,
                cmd_enabled=bool(getattr(config, 'cmd_enabled', False)),
                tmux_socket_path=tmux_socket_path,
                tmux_session_name=tmux_session_name,
                agent_name=agent_name,
                project_id=project_id,
            )
        else:
            bindings_by_agent[agent_name] = resolve_agent_binding(
                provider=spec.provider,
                agent_name=agent_name,
                workspace_path=plan.workspace_path,
                project_root=project_root,
                ensure_usable=True,
            )
        stale_binding_by_agent[agent_name] = raw_binding is not None and bindings_by_agent[agent_name] is None
        if restore_store.load(agent_name) is None:
            restore_store.save(
                agent_name,
                _build_restore_state(policy.restore_mode.value),
            )

    if interactive_tmux_layout:
        set_tmux_ui_active(True)
        launch_targets = tuple(agent_name for agent_name in targets if bindings_by_agent[agent_name] is None)
        if launch_targets:
            actions_taken.append(f'prepare_tmux_layout:{",".join(launch_targets)}')
        tmux_layout = _prepare_start_layout(
            context,
            config=config,
            targets=launch_targets,
            layout_plan=(
                build_project_layout_plan(config, target_agent_names=launch_targets)
                if launch_targets
                else None
            ),
            tmux_backend=tmux_backend,
            root_pane_id=root_pane_id,
        )
    else:
        tmux_layout = TmuxStartLayout(cmd_pane_id=None, agent_panes={})
    active_panes_by_socket: dict[str | None, list[str]] = {}
    project_socket_active_panes: list[str] = []
    cmd_pane_id = tmux_layout.cmd_pane_id
    if cmd_pane_id is None and tmux_socket_path is not None and bool(getattr(config, 'cmd_enabled', False)):
        cmd_pane_id = root_pane_id
    if cmd_pane_id and tmux_socket_path is not None:
        project_socket_active_panes.append(cmd_pane_id)
    if fresh_namespace and cmd_pane_id is not None:
        bootstrapped_cmd_pane = _bootstrap_project_namespace_cmd_pane(
            pane_id=cmd_pane_id,
            project_root=project_root,
            project_id=project_id,
            tmux_socket_path=tmux_socket_path,
            namespace_epoch=namespace_epoch,
        )
        if bootstrapped_cmd_pane is not None:
            actions_taken.append(f'bootstrap_cmd_pane:{bootstrapped_cmd_pane}')

    for style_index, agent_name in enumerate(targets):
        spec = config.agents[agent_name]
        plan = plans_by_agent[agent_name]
        binding = bindings_by_agent[agent_name]
        stale_binding = stale_binding_by_agent[agent_name]
        launch = None
        agent_action = 'attached'
        if binding is None:
            launch = ensure_agent_runtime(
                context,
                command,
                spec,
                plan,
                _launch_binding_hint(
                    binding=binding,
                    raw_binding=raw_bindings_by_agent.get(agent_name),
                    stale_binding=stale_binding,
                    assigned_pane_id=tmux_layout.agent_panes.get(agent_name),
                    tmux_socket_path=tmux_socket_path,
                ),
                assigned_pane_id=tmux_layout.agent_panes.get(agent_name),
                style_index=style_index,
                tmux_socket_path=tmux_socket_path,
            )
            binding = launch.binding
            agent_action = 'relaunched' if stale_binding and launch.launched else 'launched' if launch.launched else 'attached'
        else:
            agent_action = 'attached'

        if binding is not None:
            relabeled_pane = _relabel_project_namespace_pane(
                binding=binding,
                agent_name=agent_name,
                project_id=project_id,
                style_index=style_index,
                tmux_socket_path=tmux_socket_path,
                namespace_epoch=namespace_epoch,
            )
            if relabeled_pane is not None:
                actions_taken.append(f'relabel_runtime_pane:{agent_name}:{relabeled_pane}')

        if binding is None and stale_binding:
            runtime_ref = ''
            session_ref = ''
            health = 'degraded'
            lifecycle_state = 'degraded'
            agent_action = 'degraded'
            actions_taken.append(f'degraded_stale_binding:{agent_name}')
        else:
            runtime_ref = binding.runtime_ref if binding else None
            session_ref = binding.session_ref if binding else None
            health = 'healthy'
            lifecycle_state = 'idle'
            if agent_action == 'attached':
                actions_taken.append(f'reuse_binding:{agent_name}')
            elif agent_action == 'launched':
                actions_taken.append(f'launch_runtime:{agent_name}')
            elif agent_action == 'relaunched':
                actions_taken.append(f'relaunch_runtime:{agent_name}')

        if runtime_ref and str(runtime_ref).startswith('tmux:') and binding is not None:
            runtime_pane_id = str(runtime_ref)[len('tmux:') :]
            socket_name = binding.tmux_socket_path or binding.tmux_socket_name
            active_panes_by_socket.setdefault(socket_name, []).append(runtime_pane_id)
            if same_tmux_socket_path(getattr(binding, 'tmux_socket_path', None), tmux_socket_path):
                project_socket_active_panes.append(runtime_pane_id)

        runtime = runtime_service.attach(
            agent_name=agent_name,
            workspace_path=str(plan.workspace_path),
            backend_type=spec.runtime_mode.value,
            runtime_ref=runtime_ref,
            session_ref=session_ref,
            health=health,
            provider=spec.provider,
            runtime_root=binding.runtime_root if binding is not None else None,
            runtime_pid=binding.runtime_pid if binding is not None else None,
            terminal_backend=binding.terminal if binding is not None else None,
            pane_id=binding.pane_id if binding is not None else None,
            active_pane_id=binding.active_pane_id if binding is not None else None,
            pane_title_marker=binding.pane_title_marker if binding is not None else None,
            pane_state=binding.pane_state if binding is not None else None,
            tmux_socket_name=binding.tmux_socket_name if binding is not None else None,
            tmux_socket_path=binding.tmux_socket_path if binding is not None else None,
            session_file=binding.session_file if binding is not None else None,
            session_id=binding.session_id if binding is not None else None,
            lifecycle_state=lifecycle_state,
            managed_by='ccbd',
            binding_source='provider-session',
        )
        if command.restore and not (binding is None and stale_binding):
            runtime_service.restore(agent_name)
            actions_taken.append(f'restore_runtime:{agent_name}')
        agent_results.append(
            CcbdStartupAgentResult(
                agent_name=agent_name,
                provider=spec.provider,
                action=agent_action,
                health=health,
                workspace_path=str(plan.workspace_path),
                runtime_ref=runtime.runtime_ref,
                session_ref=runtime.session_ref,
                lifecycle_state=runtime.lifecycle_state,
                desired_state=runtime.desired_state,
                reconcile_state=runtime.reconcile_state,
                binding_source=runtime.binding_source.value,
                terminal_backend=runtime.terminal_backend,
                tmux_socket_name=runtime.tmux_socket_name,
                tmux_socket_path=runtime.tmux_socket_path,
                pane_id=runtime.pane_id,
                active_pane_id=runtime.active_pane_id,
                pane_state=runtime.pane_state,
                runtime_pid=runtime.runtime_pid,
                runtime_root=runtime.runtime_root,
                failure_reason='stale_binding_unresolved' if agent_action == 'degraded' else None,
            )
        )

    cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...] = ()
    if cleanup_tmux_orphans:
        active_by_socket = {key: tuple(dict.fromkeys(value)) for key, value in active_panes_by_socket.items()}
        if tmux_socket_path is not None:
            active_by_socket[tmux_socket_path] = tuple(
                pane_id
                for pane_id in dict.fromkeys(project_socket_active_panes)
                if str(pane_id).strip().startswith('%')
            )
        cleanup_summaries = cleanup_project_tmux_orphans_by_socket(
            project_id=project_id,
            active_panes_by_socket=active_by_socket,
        )
        total_killed = sum(len(item.killed_panes) for item in cleanup_summaries)
        actions_taken.append(f'cleanup_tmux_orphans:killed={total_killed}')
        TmuxCleanupHistoryStore(paths).append(
            TmuxCleanupEvent(
                event_kind='start',
                project_id=project_id,
                occurred_at=clock(),
                summaries=cleanup_summaries,
            )
        )
    return StartFlowSummary(
        project_root=str(project_root),
        project_id=project_id,
        started=targets,
        socket_path=str(paths.ccbd_socket_path),
        cleanup_summaries=cleanup_summaries,
        actions_taken=tuple(actions_taken),
        agent_results=tuple(agent_results),
    )


def _prepare_start_layout(
    context: CliContext,
    *,
    config,
    targets: tuple[str, ...],
    layout_plan=None,
    tmux_backend=None,
    root_pane_id: str | None = None,
) -> TmuxStartLayout:
    if tmux_backend is None and not _inside_tmux():
        return TmuxStartLayout(cmd_pane_id=None, agent_panes={})
    if tmux_backend is not None and root_pane_id is None:
        return TmuxStartLayout(cmd_pane_id=None, agent_panes={})
    return prepare_tmux_start_layout(
        context,
        config=config,
        targets=targets,
        layout_plan=layout_plan,
        tmux_backend=tmux_backend,
        root_pane_id=root_pane_id,
    )


def _inside_tmux() -> bool:
    return bool((os.environ.get('TMUX') or os.environ.get('TMUX_PANE') or '').strip())


def _session_root_pane(backend, session_name: str | None) -> str | None:
    if backend is None or not session_name:
        return None
    try:
        result = backend._tmux_run(  # type: ignore[attr-defined]
            ['list-panes', '-t', session_name, '-F', '#{pane_id}'],
            capture=True,
            check=True,
        )
    except Exception:
        return None
    pane_id = ((result.stdout or '').splitlines() or [''])[0].strip()
    return pane_id if pane_id.startswith('%') else None


def _usable_project_namespace_binding(
    binding,
    *,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    agent_name: str,
    project_id: str,
) -> object | None:
    if binding is None:
        return None
    runtime_ref = str(getattr(binding, 'runtime_ref', None) or '').strip()
    pane_state = str(getattr(binding, 'pane_state', None) or '').strip().lower()
    if not runtime_ref.startswith('tmux:'):
        return None
    if pane_state != 'alive':
        return None
    if not same_tmux_socket_path(getattr(binding, 'tmux_socket_path', None), tmux_socket_path):
        return None
    pane_id = str(getattr(binding, 'active_pane_id', None) or getattr(binding, 'pane_id', None) or '').strip()
    if not pane_id.startswith('%'):
        return None
    if not str(tmux_session_name or '').strip():
        return None
    try:
        backend = TmuxBackend(socket_path=tmux_socket_path)
    except TypeError:
        backend = TmuxBackend()
    record = inspect_project_namespace_pane(backend, pane_id)
    if record is None:
        return None
    if not record.matches(
        tmux_session_name=str(tmux_session_name),
        project_id=project_id,
        role='agent',
        slot_key=agent_name,
        managed_by='ccbd',
    ):
        return None
    return binding


def _usable_project_binding(
    binding,
    *,
    cmd_enabled: bool,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    agent_name: str,
    project_id: str,
):
    if cmd_enabled:
        return _usable_project_namespace_binding(
            binding,
            tmux_socket_path=tmux_socket_path,
            tmux_session_name=tmux_session_name,
            agent_name=agent_name,
            project_id=project_id,
        )
    return _usable_agent_only_project_binding(
        binding,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        agent_name=agent_name,
        project_id=project_id,
    )


def _usable_agent_only_project_binding(
    binding,
    *,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    agent_name: str,
    project_id: str,
):
    if binding is None:
        return None
    runtime_ref = str(getattr(binding, 'runtime_ref', None) or '').strip()
    if not runtime_ref.startswith('tmux:'):
        return None
    pane_id = str(getattr(binding, 'active_pane_id', None) or getattr(binding, 'pane_id', None) or '').strip()
    if not pane_id.startswith('%'):
        return None
    pane_state = str(getattr(binding, 'pane_state', None) or '').strip().lower()
    binding_socket_declared, binding_socket_path = _declared_binding_tmux_socket_path(binding)
    if not binding_socket_declared:
        return binding
    if binding_socket_path and not same_tmux_socket_path(binding_socket_path, tmux_socket_path):
        return None
    if pane_state in {'dead', 'missing', 'foreign'}:
        return None
    if same_tmux_socket_path(binding_socket_path, tmux_socket_path) and str(tmux_session_name or '').strip():
        try:
            backend = TmuxBackend(socket_path=tmux_socket_path)
        except TypeError:
            backend = TmuxBackend()
        record = inspect_project_namespace_pane(backend, pane_id)
        if record is not None:
            if record.matches(
                tmux_session_name=str(tmux_session_name),
                project_id=project_id,
                role='agent',
                slot_key=agent_name,
                managed_by='ccbd',
            ):
                return binding
            return None
    if pane_state in {'', 'alive', 'unknown'}:
        return binding
    return None


def _declared_binding_tmux_socket_path(binding) -> tuple[bool, str | None]:
    session_file = str(getattr(binding, 'session_file', None) or '').strip()
    if session_file:
        try:
            payload = json.loads(Path(session_file).read_text(encoding='utf-8-sig'))
        except Exception:
            payload = None
        if isinstance(payload, dict) and 'tmux_socket_path' in payload:
            text = str(payload.get('tmux_socket_path') or '').strip()
            return True, text or None
        return False, None
    text = str(getattr(binding, 'tmux_socket_path', None) or '').strip()
    return bool(text), text or None


def _launch_binding_hint(
    *,
    binding,
    raw_binding,
    stale_binding: bool,
    assigned_pane_id: str | None,
    tmux_socket_path: str | None,
):
    if binding is not None:
        return binding
    if not stale_binding:
        return None
    if assigned_pane_id and same_tmux_socket_path(getattr(raw_binding, 'tmux_socket_path', None), tmux_socket_path):
        return None
    return raw_binding


def _relabel_project_namespace_pane(
    *,
    binding,
    agent_name: str,
    project_id: str,
    style_index: int,
    tmux_socket_path: str | None,
    namespace_epoch: int | None,
) -> str | None:
    if not same_tmux_socket_path(getattr(binding, 'tmux_socket_path', None), tmux_socket_path):
        return None
    pane_id = str(getattr(binding, 'active_pane_id', None) or getattr(binding, 'pane_id', None) or '').strip()
    if not pane_id.startswith('%'):
        return None
    socket_path = str(tmux_socket_path or '').strip()
    if not socket_path:
        return None
    try:
        backend = TmuxBackend(socket_path=socket_path)
    except TypeError:
        backend = TmuxBackend()
    if not callable(getattr(backend, 'set_pane_title', None)):
        return None
    if not callable(getattr(backend, 'set_pane_user_option', None)):
        return None
    apply_ccb_pane_identity(
        backend,
        pane_id,
        title=agent_name,
        agent_label=agent_name,
        project_id=project_id,
        order_index=style_index,
        slot_key=agent_name,
        namespace_epoch=namespace_epoch,
        managed_by='ccbd',
    )
    return pane_id


def _bootstrap_project_namespace_cmd_pane(
    *,
    pane_id: str,
    project_root: Path,
    project_id: str,
    tmux_socket_path: str | None,
    namespace_epoch: int | None,
) -> str | None:
    pane_text = str(pane_id or '').strip()
    socket_path = str(tmux_socket_path or '').strip()
    if not pane_text.startswith('%') or not socket_path:
        return None
    try:
        backend = TmuxBackend(socket_path=socket_path)
    except TypeError:
        backend = TmuxBackend()
    respawn = getattr(backend, 'respawn_pane', None)
    if not callable(respawn):
        return None
    respawn(
        pane_text,
        cmd=_cmd_bootstrap_command(),
        cwd=str(project_root),
        remain_on_exit=False,
    )
    apply_ccb_pane_identity(
        backend,
        pane_text,
        title='cmd',
        agent_label='cmd',
        project_id=project_id,
        is_cmd=True,
        slot_key='cmd',
        namespace_epoch=namespace_epoch,
        managed_by='ccbd',
    )
    return pane_text


def _cmd_bootstrap_command() -> str:
    return (
        'if [ -n "${SHELL:-}" ]; then exec "$SHELL" -l; fi; '
        'if command -v bash >/dev/null 2>&1; then exec bash -l; fi; '
        'exec sh'
    )


def _build_restore_state(mode: str):
    from agents.models import AgentRestoreState, RestoreMode, RestoreStatus

    status_map = {
        'fresh': RestoreStatus.FRESH,
        'provider': RestoreStatus.PROVIDER,
        'auto': RestoreStatus.CHECKPOINT,
        'attach': RestoreStatus.CHECKPOINT,
        'memory': RestoreStatus.CHECKPOINT,
    }
    restore_mode = RestoreMode.AUTO if mode == 'auto' else RestoreMode.FRESH if mode == 'fresh' else RestoreMode.PROVIDER if mode == 'provider' else RestoreMode.AUTO
    return AgentRestoreState(
        restore_mode=restore_mode,
        last_checkpoint=None,
        conversation_summary='bootstrap placeholder',
        open_tasks=[],
        files_touched=[],
        base_commit=None,
        head_commit=None,
        last_restore_status=status_map.get(mode, RestoreStatus.CHECKPOINT),
    )


__all__ = ['StartFlowSummary', 'run_start_flow']
