from __future__ import annotations

from pathlib import Path

from terminal_runtime.tmux_identity import apply_ccb_pane_identity

from .tmux_backend import prepared_state, run_cwd, tmux_backend
from .tmux_panes import (
    best_effort_kill_tmux_pane,
    create_detached_tmux_pane,
    launch_pane,
    pane_meets_minimum_size,
    prepare_detached_tmux_server,
)


def launch_tmux_runtime(
    context,
    command,
    spec,
    plan,
    launcher,
    *,
    backend_factory,
    pane_title_marker_fn,
    launch_session_id_fn,
    create_detached_tmux_pane_fn,
    pane_meets_minimum_size_fn,
    best_effort_kill_tmux_pane_fn,
    write_session_file_fn,
    assigned_pane_id: str | None = None,
    style_index: int = 0,
    tmux_socket_path: str | None = None,
    allow_detached_fallback: bool = True,
) -> None:
    runtime_dir = context.paths.agent_dir(spec.name) / 'provider-runtime' / spec.provider
    runtime_dir.mkdir(parents=True, exist_ok=True)
    launch_session_id = launch_session_id_fn(spec.name)
    prepared = prepared_state(launcher, runtime_dir)
    backend = tmux_backend(backend_factory, tmux_socket_path)
    pane_title_marker = pane_title_marker_fn(context, spec)
    start_cmd = launcher.build_start_cmd(command, spec, runtime_dir, launch_session_id)
    runtime_cwd = run_cwd(
        launcher,
        command=command,
        spec=spec,
        plan=plan,
        runtime_dir=runtime_dir,
        launch_session_id=launch_session_id,
    )
    pane_id = launch_pane(
        backend,
        spec_name=spec.name,
        assigned_pane_id=assigned_pane_id,
        start_cmd=start_cmd,
        run_cwd=runtime_cwd,
        create_detached_tmux_pane_fn=create_detached_tmux_pane_fn,
        pane_meets_minimum_size_fn=pane_meets_minimum_size_fn,
        best_effort_kill_tmux_pane_fn=best_effort_kill_tmux_pane_fn,
        allow_detached_fallback=allow_detached_fallback,
    )
    apply_ccb_pane_identity(
        backend,
        pane_id,
        title=spec.name,
        agent_label=spec.name,
        project_id=context.project.project_id,
        order_index=style_index,
        slot_key=spec.name,
    )

    provider_payload = launcher.build_session_payload(
        context=context,
        spec=spec,
        plan=plan,
        runtime_dir=runtime_dir,
        run_cwd=runtime_cwd,
        pane_id=pane_id,
        pane_title_marker=pane_title_marker,
        start_cmd=start_cmd,
        launch_session_id=launch_session_id,
        prepared_state=prepared,
    )
    write_session_file_fn(
        context=context,
        spec=spec,
        plan=plan,
        runtime_dir=runtime_dir,
        run_cwd=runtime_cwd,
        pane_id=pane_id,
        tmux_socket_name=str(getattr(backend, '_socket_name', '') or '').strip() or None,
        tmux_socket_path=str(getattr(backend, '_socket_path', '') or '').strip() or None,
        pane_title_marker=pane_title_marker,
        start_cmd=start_cmd,
        launch_session_id=launch_session_id,
        provider_payload=provider_payload,
    )
    if launcher.post_launch is not None:
        launcher.post_launch(
            backend,
            pane_id,
            runtime_dir,
            launch_session_id,
            prepared,
        )


__all__ = [
    'best_effort_kill_tmux_pane',
    'create_detached_tmux_pane',
    'launch_tmux_runtime',
    'pane_meets_minimum_size',
    'prepare_detached_tmux_server',
]
