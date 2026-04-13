from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from cli.context import CliContext
from cli.models import ParsedKillCommand, ParsedStartCommand
from cli.services.daemon import shutdown_daemon
from cli.services.kill import kill_project
from cli.services.tmux_ui import set_tmux_ui_active
from ccbd.services.project_namespace import ProjectNamespaceController
from project.ids import compute_project_id
from project.resolver import ProjectContext
from storage.paths import PathLayout


@dataclass(frozen=True)
class ResetProjectSummary:
    project_root: str
    project_id: str
    preserved_config: bool
    reset_performed: bool


def reset_project_state(project_root: Path, *, context: CliContext | None = None) -> ResetProjectSummary:
    root = _resolve_path(project_root)
    layout = PathLayout(root)
    project_id = compute_project_id(root)
    preserved_config_text = _read_optional_text(layout.config_path)
    reset_performed = False

    if layout.ccb_dir.exists():
        reset_performed = True
        _stop_project_runtime(context or _build_reset_context(root))
        _clear_anchor(layout.ccb_dir)
        if preserved_config_text is not None:
            layout.ccb_dir.mkdir(parents=True, exist_ok=True)
            layout.config_path.write_text(preserved_config_text, encoding='utf-8')

    return ResetProjectSummary(
        project_root=str(root),
        project_id=project_id,
        preserved_config=preserved_config_text is not None,
        reset_performed=reset_performed,
    )


def _build_reset_context(project_root: Path) -> CliContext:
    root = _resolve_path(project_root)
    project_id = compute_project_id(root)
    command = ParsedStartCommand(
        project=str(root),
        agent_names=(),
        restore=True,
        auto_permission=True,
        reset_context=True,
    )
    project = ProjectContext(
        cwd=root,
        project_root=root,
        config_dir=root / '.ccb',
        project_id=project_id,
        source='reset',
    )
    return CliContext(
        command=command,
        cwd=root,
        project=project,
        paths=PathLayout(root),
    )


def _stop_project_runtime(context: CliContext) -> None:
    cleanup_errors: list[str] = []
    try:
        kill_project(
            context,
            ParsedKillCommand(
                project=str(context.project.project_root),
                force=True,
            ),
        )
        set_tmux_ui_active(False)
        return
    except Exception as exc:
        cleanup_errors.append(f'kill_project: {exc}')

    daemon_stopped = False
    try:
        shutdown_daemon(context, force=True)
        daemon_stopped = True
    except Exception as exc:
        cleanup_errors.append(f'shutdown_daemon: {exc}')

    namespace_destroyed = False
    try:
        ProjectNamespaceController(context.paths, context.project.project_id).destroy(
            reason='reset',
            force=True,
        )
        namespace_destroyed = True
    except Exception as exc:
        cleanup_errors.append(f'namespace_destroy: {exc}')

    set_tmux_ui_active(False)
    if daemon_stopped or namespace_destroyed:
        return
    details = '; '.join(cleanup_errors) if cleanup_errors else 'unknown cleanup failure'
    raise RuntimeError(
        'failed to stop project runtime before rebuilding `.ccb`; '
        f'{details}. Run `ccb kill -f` from the project root and retry `ccb -n`.'
    )


def _clear_anchor(ccb_dir: Path) -> None:
    if ccb_dir.is_symlink() or ccb_dir.is_file():
        ccb_dir.unlink()
        return
    if ccb_dir.is_dir():
        shutil.rmtree(ccb_dir)


def _read_optional_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding='utf-8')


def _resolve_path(path: Path) -> Path:
    candidate = Path(path).expanduser()
    try:
        return candidate.resolve()
    except Exception:
        return candidate.absolute()


__all__ = ['ResetProjectSummary', 'reset_project_state']
