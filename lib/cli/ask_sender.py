from __future__ import annotations

from cli.context import CliContext
from mailbox_runtime.targets import USER_ACTOR
from workspace.actors import resolve_workspace_actor


def resolve_ask_sender(context: CliContext, explicit_sender: str | None) -> str:
    sender = str(explicit_sender or '').strip()
    if sender:
        return sender

    workspace_actor = resolve_workspace_actor(context.cwd, project_id=context.project.project_id)
    if workspace_actor:
        return workspace_actor
    return USER_ACTOR


__all__ = ['resolve_ask_sender']
