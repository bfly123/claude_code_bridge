from __future__ import annotations

import os
import time
from pathlib import Path

from terminal_runtime.tmux_identity import apply_ccb_pane_identity


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
    runtime_dir = context.paths.agent_dir(spec.name) / "provider-runtime" / spec.provider
    runtime_dir.mkdir(parents=True, exist_ok=True)
    launch_session_id = launch_session_id_fn(spec.name)
    prepared_state = _prepared_state(launcher, runtime_dir)
    backend = _tmux_backend(backend_factory, tmux_socket_path)
    pane_title_marker = pane_title_marker_fn(context, spec)
    start_cmd = launcher.build_start_cmd(command, spec, runtime_dir, launch_session_id)
    run_cwd = _run_cwd(
        launcher,
        command=command,
        spec=spec,
        plan=plan,
        runtime_dir=runtime_dir,
        launch_session_id=launch_session_id,
    )
    pane_id = _launch_pane(
        backend,
        spec_name=spec.name,
        assigned_pane_id=assigned_pane_id,
        start_cmd=start_cmd,
        run_cwd=run_cwd,
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
        run_cwd=run_cwd,
        pane_id=pane_id,
        pane_title_marker=pane_title_marker,
        start_cmd=start_cmd,
        launch_session_id=launch_session_id,
        prepared_state=prepared_state,
    )
    write_session_file_fn(
        context=context,
        spec=spec,
        plan=plan,
        runtime_dir=runtime_dir,
        run_cwd=run_cwd,
        pane_id=pane_id,
        tmux_socket_name=str(getattr(backend, '_socket_name', '') or '').strip() or None,
        tmux_socket_path=str(getattr(backend, '_socket_path', '') or '').strip() or None,
        pane_title_marker=pane_title_marker,
        start_cmd=start_cmd,
        launch_session_id=launch_session_id,
        provider_payload=provider_payload,
    )
    if launcher.post_launch is not None:
        launcher.post_launch(backend, pane_id, runtime_dir, launch_session_id, prepared_state)


def _prepared_state(launcher, runtime_dir: Path) -> dict:
    if launcher.prepare_runtime is None:
        return {}
    return dict(launcher.prepare_runtime(runtime_dir) or {})


def _tmux_backend(backend_factory, tmux_socket_path: str | None):
    if tmux_socket_path is None:
        return backend_factory()
    try:
        return backend_factory(socket_path=tmux_socket_path)
    except TypeError:
        return backend_factory()


def _run_cwd(
    launcher,
    *,
    command,
    spec,
    plan,
    runtime_dir: Path,
    launch_session_id: str,
) -> Path:
    run_cwd = Path(plan.workspace_path)
    if launcher.resolve_run_cwd is None:
        return run_cwd
    resolved = launcher.resolve_run_cwd(
        command,
        spec,
        plan,
        runtime_dir,
        launch_session_id,
    )
    if resolved is None:
        return run_cwd
    return Path(resolved)


def _launch_pane(
    backend,
    *,
    spec_name: str,
    assigned_pane_id: str | None,
    start_cmd: str,
    run_cwd: Path,
    create_detached_tmux_pane_fn,
    pane_meets_minimum_size_fn,
    best_effort_kill_tmux_pane_fn,
    allow_detached_fallback: bool,
) -> str:
    if assigned_pane_id:
        pane_id = str(assigned_pane_id)
        backend.respawn_pane(pane_id, cmd=start_cmd, cwd=str(run_cwd), remain_on_exit=True)
        return pane_id
    if not allow_detached_fallback:
        raise RuntimeError(f'project namespace launch requires assigned tmux pane for {spec_name}')
    return _allocate_fresh_pane(
        backend,
        spec_name=spec_name,
        start_cmd=start_cmd,
        run_cwd=run_cwd,
        create_detached_tmux_pane_fn=create_detached_tmux_pane_fn,
        pane_meets_minimum_size_fn=pane_meets_minimum_size_fn,
        best_effort_kill_tmux_pane_fn=best_effort_kill_tmux_pane_fn,
        allow_detached_fallback=allow_detached_fallback,
    )


def _allocate_fresh_pane(
    backend,
    *,
    spec_name: str,
    start_cmd: str,
    run_cwd: Path,
    create_detached_tmux_pane_fn,
    pane_meets_minimum_size_fn,
    best_effort_kill_tmux_pane_fn,
    allow_detached_fallback: bool,
) -> str:
    try:
        pane_id = backend.create_pane(start_cmd, str(run_cwd))
    except Exception as exc:
        if not _should_fallback_to_detached_session(exc):
            raise
        return _detached_pane(
            backend,
            spec_name=spec_name,
            start_cmd=start_cmd,
            run_cwd=run_cwd,
            create_detached_tmux_pane_fn=create_detached_tmux_pane_fn,
        )
    if pane_meets_minimum_size_fn(backend, pane_id):
        return pane_id
    best_effort_kill_tmux_pane_fn(backend, pane_id)
    if not allow_detached_fallback:
        raise RuntimeError(
            f'project namespace launch could not allocate stable tmux pane for {spec_name}'
        )
    return _detached_pane(
        backend,
        spec_name=spec_name,
        start_cmd=start_cmd,
        run_cwd=run_cwd,
        create_detached_tmux_pane_fn=create_detached_tmux_pane_fn,
    )


def _detached_pane(
    backend,
    *,
    spec_name: str,
    start_cmd: str,
    run_cwd: Path,
    create_detached_tmux_pane_fn,
) -> str:
    return create_detached_tmux_pane_fn(
        backend,
        cmd=start_cmd,
        cwd=run_cwd,
        session_name=f"ccb-{spec_name}",
    )


def prepare_detached_tmux_server(backend) -> None:
    _best_effort_tmux_run(backend, ["start-server"])
    _best_effort_tmux_run(backend, ["set-option", "-g", "destroy-unattached", "off"])


def _best_effort_tmux_run(backend, argv: list[str]) -> None:
    try:
        backend._tmux_run(argv, check=False)  # type: ignore[attr-defined]
    except Exception:
        pass


def create_detached_tmux_pane(backend, *, cmd: str, cwd: Path, session_name: str) -> str:
    target_session = f"{session_name}-{int(time.time() * 1000)}-{os.getpid()}"
    prepare_detached_tmux_server(backend)
    backend._tmux_run(  # type: ignore[attr-defined]
        ["new-session", "-d", "-x", "160", "-y", "48", "-s", target_session, "-c", str(cwd)],
        check=True,
    )
    result = backend._tmux_run(  # type: ignore[attr-defined]
        ["list-panes", "-t", target_session, "-F", "#{pane_id}"],
        capture=True,
        check=True,
    )
    pane_id = ((result.stdout or "").splitlines() or [""])[0].strip()
    if not pane_id:
        raise RuntimeError(f"failed to create detached tmux pane for session {target_session}")
    backend.respawn_pane(pane_id, cmd=cmd, cwd=str(cwd), remain_on_exit=True)
    return pane_id


def pane_meets_minimum_size(
    backend,
    pane_id: str,
    *,
    min_width: int = 20,
    min_height: int = 8,
) -> bool:
    dimensions = _pane_dimensions(backend, pane_id)
    if dimensions is None:
        return True
    width, height = dimensions
    return width >= min_width and height >= min_height


def _pane_dimensions(backend, pane_id: str) -> tuple[int, int] | None:
    try:
        result = backend._tmux_run(  # type: ignore[attr-defined]
            ["display-message", "-p", "-t", pane_id, "#{pane_width}x#{pane_height}"],
            capture=True,
            check=True,
        )
    except Exception:
        return None
    raw = (result.stdout or "").strip().lower()
    try:
        width_text, height_text = raw.split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except Exception:
        return None
    return width, height


def best_effort_kill_tmux_pane(backend, pane_id: str) -> None:
    try:
        backend.kill_tmux_pane(pane_id)
        return
    except Exception:
        pass
    try:
        backend._tmux_run(["kill-pane", "-t", pane_id], check=False)  # type: ignore[attr-defined]
    except Exception:
        pass


def _should_fallback_to_detached_session(exc: Exception) -> bool:
    text = str(exc).strip().lower()
    return "split-window failed" in text or "no space for new pane" in text


__all__ = [
    "best_effort_kill_tmux_pane",
    "create_detached_tmux_pane",
    "launch_tmux_runtime",
    "pane_meets_minimum_size",
    "prepare_detached_tmux_server",
]
