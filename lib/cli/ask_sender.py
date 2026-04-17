from __future__ import annotations

import os
from pathlib import Path

from agents.config_loader import load_project_config
from agents.models import AgentValidationError, normalize_agent_name
from cli.context import CliContext
from mailbox_runtime.targets import CMD_ACTOR, USER_ACTOR
from workspace.actors import resolve_workspace_actor


def resolve_ask_sender(context: CliContext, explicit_sender: str | None) -> str:
    sender = str(explicit_sender or '').strip()
    if sender:
        return sender

    config = load_project_config(context.project.project_root).config
    allowed_session_actors = frozenset(
        {
            *[normalize_agent_name(name) for name in getattr(config, 'agents', {}) or {}],
            *([CMD_ACTOR] if bool(getattr(config, 'cmd_enabled', False)) else []),
        }
    )
    session_actor = _resolve_session_actor(context, allowed_session_actors=allowed_session_actors)
    if session_actor:
        return session_actor

    workspace_actor = resolve_workspace_actor(context.cwd, project_id=context.project.project_id)
    if workspace_actor:
        return workspace_actor

    if bool(getattr(config, 'cmd_enabled', False)):
        return CMD_ACTOR
    return USER_ACTOR


def _resolve_session_actor(context: CliContext, *, allowed_session_actors: frozenset[str]) -> str | None:
    for env_name in ('CCB_CALLER_ACTOR',):
        actor = _normalized_actor_candidate(os.environ.get(env_name))
        if actor in allowed_session_actors:
            return actor

    for env_name in ('CCB_CALLER_RUNTIME_DIR', 'CODEX_RUNTIME_DIR'):
        actor = _actor_from_runtime_dir(
            os.environ.get(env_name),
            project_root=context.project.project_root,
            allowed_session_actors=allowed_session_actors,
        )
        if actor is not None:
            return actor

    return _actor_from_session_id(os.environ.get('CCB_SESSION_ID'), allowed_session_actors=allowed_session_actors)


def _actor_from_runtime_dir(
    value: str | None,
    *,
    project_root: Path,
    allowed_session_actors: frozenset[str],
) -> str | None:
    runtime_dir = str(value or '').strip()
    if not runtime_dir:
        return None
    resolved_runtime_dir = _resolve_path(Path(runtime_dir))
    resolved_project_root = _resolve_path(project_root)
    try:
        resolved_runtime_dir.relative_to(resolved_project_root)
    except ValueError:
        return None
    parts = resolved_runtime_dir.parts
    for index, part in enumerate(parts[:-2]):
        if part != '.ccb':
            continue
        if parts[index + 1] != 'agents':
            continue
        candidate = _normalized_actor_candidate(parts[index + 2])
        if candidate in allowed_session_actors:
            return candidate
    return None


def _actor_from_session_id(value: str | None, *, allowed_session_actors: frozenset[str]) -> str | None:
    session_id = str(value or '').strip().lower()
    if not session_id.startswith('ccb-'):
        return None
    suffix = session_id[4:]
    matches = [actor for actor in allowed_session_actors if suffix == actor or suffix.startswith(f'{actor}-')]
    if not matches:
        return None
    return max(matches, key=len)


def _normalized_actor_candidate(value: str | None) -> str | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return normalize_agent_name(text)
    except AgentValidationError:
        lowered = text.lower()
        if lowered == CMD_ACTOR:
            return lowered
        return None


def _resolve_path(path: Path) -> Path:
    current = Path(path).expanduser()
    try:
        return current.resolve()
    except Exception:
        return current.absolute()


__all__ = ['resolve_ask_sender']
