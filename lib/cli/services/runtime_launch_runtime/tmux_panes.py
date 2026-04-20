from __future__ import annotations

import os
import time
from pathlib import Path


def launch_pane(
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
        backend.respawn_pane(
            pane_id,
            cmd=start_cmd,
            cwd=str(run_cwd),
            remain_on_exit=True,
        )
        return pane_id
    if not allow_detached_fallback:
        raise RuntimeError(
            f'project namespace launch requires assigned tmux pane for {spec_name}'
        )
    return allocate_fresh_pane(
        backend,
        spec_name=spec_name,
        start_cmd=start_cmd,
        run_cwd=run_cwd,
        create_detached_tmux_pane_fn=create_detached_tmux_pane_fn,
        pane_meets_minimum_size_fn=pane_meets_minimum_size_fn,
        best_effort_kill_tmux_pane_fn=best_effort_kill_tmux_pane_fn,
        allow_detached_fallback=allow_detached_fallback,
    )


def allocate_fresh_pane(
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
        if not should_fallback_to_detached_session(exc):
            raise
        return detached_pane(
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
    return detached_pane(
        backend,
        spec_name=spec_name,
        start_cmd=start_cmd,
        run_cwd=run_cwd,
        create_detached_tmux_pane_fn=create_detached_tmux_pane_fn,
    )


def detached_pane(
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
        session_name=f'ccb-{spec_name}',
    )


def prepare_detached_tmux_server(backend) -> None:
    best_effort_tmux_run(backend, ['start-server'])
    best_effort_tmux_run(backend, ['set-option', '-g', 'destroy-unattached', 'off'])


def best_effort_tmux_run(backend, argv: list[str]) -> None:
    try:
        backend._tmux_run(argv, check=False)  # type: ignore[attr-defined]
    except Exception:
        pass


def create_detached_tmux_pane(backend, *, cmd: str, cwd: Path, session_name: str) -> str:
    target_session = f'{session_name}-{int(time.time() * 1000)}-{os.getpid()}'
    prepare_detached_tmux_server(backend)
    backend._tmux_run(  # type: ignore[attr-defined]
        ['new-session', '-d', '-x', '160', '-y', '48', '-s', target_session, '-c', str(cwd)],
        check=True,
    )
    result = backend._tmux_run(  # type: ignore[attr-defined]
        ['list-panes', '-t', target_session, '-F', '#{pane_id}'],
        capture=True,
        check=True,
    )
    pane_id = ((result.stdout or '').splitlines() or [''])[0].strip()
    if not pane_id:
        raise RuntimeError(
            f'failed to create detached tmux pane for session {target_session}'
        )
    backend.respawn_pane(pane_id, cmd=cmd, cwd=str(cwd), remain_on_exit=True)
    return pane_id


def pane_meets_minimum_size(
    backend,
    pane_id: str,
    *,
    min_width: int = 20,
    min_height: int = 8,
) -> bool:
    dimensions = pane_dimensions(backend, pane_id)
    if dimensions is None:
        return True
    width, height = dimensions
    return width >= min_width and height >= min_height


def pane_dimensions(backend, pane_id: str) -> tuple[int, int] | None:
    try:
        result = backend._tmux_run(  # type: ignore[attr-defined]
            ['display-message', '-p', '-t', pane_id, '#{pane_width}x#{pane_height}'],
            capture=True,
            check=True,
        )
    except Exception:
        return None
    raw = (result.stdout or '').strip().lower()
    try:
        width_text, height_text = raw.split('x', 1)
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
        backend._tmux_run(['kill-pane', '-t', pane_id], check=False)  # type: ignore[attr-defined]
    except Exception:
        pass


def should_fallback_to_detached_session(exc: Exception) -> bool:
    text = str(exc).strip().lower()
    return 'split-window failed' in text or 'no space for new pane' in text


__all__ = [
    'best_effort_kill_tmux_pane',
    'create_detached_tmux_pane',
    'launch_pane',
    'pane_meets_minimum_size',
    'prepare_detached_tmux_server',
]
