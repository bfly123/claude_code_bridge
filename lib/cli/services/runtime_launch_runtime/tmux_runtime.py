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
    prepared_state = dict(launcher.prepare_runtime(runtime_dir) or {}) if launcher.prepare_runtime else {}

    if tmux_socket_path is not None:
        try:
            backend = backend_factory(socket_path=tmux_socket_path)
        except TypeError:
            backend = backend_factory()
    else:
        backend = backend_factory()
    pane_title_marker = pane_title_marker_fn(context, spec)
    start_cmd = launcher.build_start_cmd(command, spec, runtime_dir, launch_session_id)
    run_cwd = Path(plan.workspace_path)
    if launcher.resolve_run_cwd is not None:
        resolved_run_cwd = launcher.resolve_run_cwd(command, spec, plan, runtime_dir, launch_session_id)
        if resolved_run_cwd is not None:
            run_cwd = Path(resolved_run_cwd)
    if assigned_pane_id:
        pane_id = str(assigned_pane_id)
        backend.respawn_pane(pane_id, cmd=start_cmd, cwd=str(run_cwd), remain_on_exit=True)
    else:
        if not allow_detached_fallback:
            raise RuntimeError(
                f'project namespace launch requires assigned tmux pane for {spec.name}'
            )
        try:
            pane_id = backend.create_pane(start_cmd, str(run_cwd))
        except Exception as exc:
            if not _should_fallback_to_detached_session(exc):
                raise
            pane_id = create_detached_tmux_pane_fn(
                backend,
                cmd=start_cmd,
                cwd=run_cwd,
                session_name=f"ccb-{spec.name}",
            )
        else:
            if not pane_meets_minimum_size_fn(backend, pane_id):
                best_effort_kill_tmux_pane_fn(backend, pane_id)
                if not allow_detached_fallback:
                    raise RuntimeError(
                        f'project namespace launch could not allocate stable tmux pane for {spec.name}'
                    )
                pane_id = create_detached_tmux_pane_fn(
                    backend,
                    cmd=start_cmd,
                    cwd=run_cwd,
                    session_name=f"ccb-{spec.name}",
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


def prepare_detached_tmux_server(backend) -> None:
    try:
        backend._tmux_run(["start-server"], check=False)  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        backend._tmux_run(["set-option", "-g", "destroy-unattached", "off"], check=False)  # type: ignore[attr-defined]
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


def pane_meets_minimum_size(backend, pane_id: str, *, min_width: int = 20, min_height: int = 8) -> bool:
    try:
        result = backend._tmux_run(  # type: ignore[attr-defined]
            ["display-message", "-p", "-t", pane_id, "#{pane_width}x#{pane_height}"],
            capture=True,
            check=True,
        )
    except Exception:
        return True
    raw = (result.stdout or "").strip().lower()
    try:
        width_text, height_text = raw.split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except Exception:
        return True
    return width >= min_width and height >= min_height


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
