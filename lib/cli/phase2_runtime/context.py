from __future__ import annotations

from pathlib import Path


def build_context(command, *, cwd: Path | None, out, builder_cls, reset_project_state_fn, project_discovery_error_cls, confirm_project_reset_fn):
    if getattr(command, 'kind', None) == 'start' and getattr(command, 'reset_context', False):
        return build_reset_start_context(
            command,
            cwd=cwd,
            out=out,
            builder_cls=builder_cls,
            reset_project_state_fn=reset_project_state_fn,
            project_discovery_error_cls=project_discovery_error_cls,
            confirm_project_reset_fn=confirm_project_reset_fn,
        )
    return builder_cls().build(
        command,
        cwd=cwd,
        bootstrap_if_missing=command.kind != 'config-validate',
    )


def build_reset_start_context(
    command,
    *,
    cwd: Path | None,
    out,
    builder_cls,
    reset_project_state_fn,
    project_discovery_error_cls,
    confirm_project_reset_fn,
):
    current = Path(cwd or Path.cwd()).expanduser()
    try:
        current = current.resolve()
    except Exception:
        current = current.absolute()

    existing_context = resolve_existing_context(
        command,
        cwd=current,
        builder_cls=builder_cls,
        project_discovery_error_cls=project_discovery_error_cls,
    )
    project_root = (
        existing_context.project.project_root
        if existing_context is not None
        else resolve_requested_project_root(
            command,
            cwd=current,
            project_discovery_error_cls=project_discovery_error_cls,
        )
    )
    confirm_project_reset_fn(project_root, out=out)
    reset_project_state_fn(project_root, context=existing_context)
    return builder_cls().build(
        command,
        cwd=current,
        bootstrap_if_missing=True,
    )


def resolve_existing_context(command, *, cwd: Path, builder_cls, project_discovery_error_cls):
    try:
        return builder_cls().build(
            command,
            cwd=cwd,
            bootstrap_if_missing=False,
        )
    except project_discovery_error_cls:
        return None


def resolve_requested_project_root(command, *, cwd: Path, project_discovery_error_cls):
    root = Path(command.project).expanduser() if command.project else cwd
    try:
        root = root.resolve()
    except Exception:
        root = root.absolute()
    if not root.exists() or not root.is_dir():
        raise project_discovery_error_cls(f'project root not found: {root}')
    return root


def confirm_project_reset(project_root: Path, *, out, stdin, stream_is_tty_fn) -> None:
    if not stream_is_tty_fn(stdin):
        raise RuntimeError('ccb -n requires interactive confirmation on stdin')
    print(
        f'Refresh project memory/context under {project_root / ".ccb"}? [y/N] ',
        end='',
        file=out,
        flush=True,
    )
    reply = stdin.readline()
    if str(reply or '').strip().lower() not in {'y', 'yes'}:
        raise RuntimeError('project reset cancelled')


__all__ = [
    'build_context',
    'build_reset_start_context',
    'confirm_project_reset',
    'resolve_existing_context',
    'resolve_requested_project_root',
]
