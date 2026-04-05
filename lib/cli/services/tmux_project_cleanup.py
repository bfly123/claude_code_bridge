from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import shutil
from dataclasses import dataclass

from terminal_runtime import TmuxBackend


@dataclass(frozen=True)
class ProjectTmuxCleanupSummary:
    socket_name: str | None
    owned_panes: tuple[str, ...]
    active_panes: tuple[str, ...]
    orphaned_panes: tuple[str, ...]
    killed_panes: tuple[str, ...]


def list_project_tmux_panes(
    *,
    project_id: str,
    socket_name: str | None = None,
    backend_factory=TmuxBackend,
) -> tuple[str, ...]:
    project_id = str(project_id or '').strip()
    if not project_id or shutil.which('tmux') is None:
        return ()

    backend = _build_backend(backend_factory, socket_name=socket_name)
    if backend is None:
        return ()

    lister = getattr(backend, 'list_panes_by_user_options', None)
    if not callable(lister):
        return ()

    try:
        pane_ids = [
            str(item).strip()
            for item in lister({'@ccb_project_id': project_id})
            if str(item).strip().startswith('%')
        ]
    except Exception:
        return ()
    if not pane_ids:
        return ()
    return tuple(dict.fromkeys(pane_ids))


def cleanup_project_tmux_orphans(
    *,
    project_id: str,
    active_panes: tuple[str, ...] = (),
    socket_name: str | None = None,
    backend_factory=TmuxBackend,
) -> tuple[str, ...]:
    active = {str(item).strip() for item in active_panes if str(item).strip().startswith('%')}
    owned = list_project_tmux_panes(project_id=project_id, socket_name=socket_name, backend_factory=backend_factory)
    if not owned:
        return ()
    orphaned = tuple(pane for pane in owned if pane not in active)
    if not orphaned:
        return ()
    return _kill_panes(orphaned, socket_name=socket_name, backend_factory=backend_factory)


def cleanup_project_tmux_orphans_by_socket(
    *,
    project_id: str,
    active_panes_by_socket: Mapping[str | None, tuple[str, ...]],
    backend_factory=TmuxBackend,
) -> tuple[ProjectTmuxCleanupSummary, ...]:
    summaries: list[ProjectTmuxCleanupSummary] = []
    socket_names: list[str | None] = list(active_panes_by_socket)
    if None not in active_panes_by_socket:
        socket_names.append(None)
    for socket_name in socket_names:
        owned = list_project_tmux_panes(
            project_id=project_id,
            socket_name=socket_name,
            backend_factory=backend_factory,
        )
        if not owned:
            continue
        active = tuple(
            pane for pane in dict.fromkeys(active_panes_by_socket.get(socket_name, ()))
            if str(pane).strip().startswith('%')
        )
        orphaned = tuple(pane for pane in owned if pane not in set(active))
        killed = _kill_panes(orphaned, socket_name=socket_name, backend_factory=backend_factory) if orphaned else ()
        summaries.append(
            ProjectTmuxCleanupSummary(
                socket_name=socket_name,
                owned_panes=owned,
                active_panes=active,
                orphaned_panes=orphaned,
                killed_panes=killed,
            )
        )
    return tuple(summaries)


def kill_project_tmux_panes(
    *,
    project_id: str,
    socket_name: str | None = None,
    backend_factory=TmuxBackend,
) -> tuple[str, ...]:
    unique_panes = list(list_project_tmux_panes(project_id=project_id, socket_name=socket_name, backend_factory=backend_factory))
    if not unique_panes:
        return ()

    return _kill_panes(unique_panes, socket_name=socket_name, backend_factory=backend_factory)


def _build_backend(backend_factory, *, socket_name: str | None):
    resolved_socket_name, resolved_socket_path = _resolve_socket_ref(socket_name)
    try:
        return backend_factory(socket_name=resolved_socket_name, socket_path=resolved_socket_path)
    except TypeError:
        try:
            if resolved_socket_path is not None:
                try:
                    return backend_factory(socket_path=resolved_socket_path)
                except TypeError:
                    pass
            if resolved_socket_name is not None:
                try:
                    return backend_factory(socket_name=resolved_socket_name)
                except TypeError:
                    pass
            return backend_factory()
        except Exception:
            return None
    except Exception:
        return None


def _resolve_socket_ref(socket_name: str | None) -> tuple[str | None, str | None]:
    text = str(socket_name or '').strip()
    if not text:
        return None, None
    if '/' in text or '\\' in text:
        try:
            return None, str(Path(text).expanduser())
        except Exception:
            return None, text
    return text, None


def _kill_panes(
    pane_ids: list[str] | tuple[str, ...],
    *,
    socket_name: str | None = None,
    backend_factory=TmuxBackend,
) -> tuple[str, ...]:
    backend = _build_backend(backend_factory, socket_name=socket_name)
    if backend is None:
        return ()
    current_pane = str(os.environ.get('TMUX_PANE') or '').strip()
    ordered = [pane for pane in pane_ids if pane != current_pane]
    if current_pane and current_pane in pane_ids:
        ordered.append(current_pane)

    strict_kill = getattr(backend, 'kill_tmux_pane', None)
    legacy_kill = getattr(backend, 'kill_pane', None)

    killed: list[str] = []
    for pane_id in ordered:
        try:
            if callable(strict_kill):
                strict_kill(pane_id)
            elif callable(legacy_kill):
                legacy_kill(pane_id)
            else:
                continue
        except Exception:
            continue
        killed.append(pane_id)
    return tuple(killed)


__all__ = [
    'ProjectTmuxCleanupSummary',
    'cleanup_project_tmux_orphans',
    'cleanup_project_tmux_orphans_by_socket',
    'kill_project_tmux_panes',
    'list_project_tmux_panes',
]
