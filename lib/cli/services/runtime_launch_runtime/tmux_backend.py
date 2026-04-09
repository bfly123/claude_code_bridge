from __future__ import annotations

from pathlib import Path


def prepared_state(launcher, runtime_dir: Path) -> dict:
    if launcher.prepare_runtime is None:
        return {}
    return dict(launcher.prepare_runtime(runtime_dir) or {})


def tmux_backend(backend_factory, tmux_socket_path: str | None):
    if tmux_socket_path is None:
        return backend_factory()
    try:
        return backend_factory(socket_path=tmux_socket_path)
    except TypeError:
        return backend_factory()


def run_cwd(
    launcher,
    *,
    command,
    spec,
    plan,
    runtime_dir: Path,
    launch_session_id: str,
) -> Path:
    workspace_path = Path(plan.workspace_path)
    if launcher.resolve_run_cwd is None:
        return workspace_path
    resolved = launcher.resolve_run_cwd(
        command,
        spec,
        plan,
        runtime_dir,
        launch_session_id,
    )
    if resolved is None:
        return workspace_path
    return Path(resolved)


__all__ = ['prepared_state', 'run_cwd', 'tmux_backend']
