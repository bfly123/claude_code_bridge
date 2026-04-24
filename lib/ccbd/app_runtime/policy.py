from __future__ import annotations

from ccbd.services.start_policy import CcbdStartPolicy, recovery_start_options as recovery_start_options_impl


def persist_start_policy(app, *, auto_permission: bool, source: str = 'start_command') -> None:
    app.start_policy_store.save(
        CcbdStartPolicy(
            project_id=app.project_id,
            auto_permission=bool(auto_permission),
            recovery_restore=True,
            last_started_at=app.clock(),
            source=str(source or 'start_command'),
        )
    )


def recovery_start_options(app) -> tuple[bool, bool]:
    try:
        policy = app.start_policy_store.load()
    except Exception:
        policy = None
    return recovery_start_options_impl(policy)


def mount_agent_from_policy(app, agent_name: str) -> None:
    restore, auto_permission = recovery_start_options(app)
    app.runtime_supervisor.start(
        agent_names=(agent_name,),
        restore=restore,
        auto_permission=auto_permission,
        cleanup_tmux_orphans=False,
        interactive_tmux_layout=False,
        background_maintenance=True,
    )


def remount_project_from_policy(app, reason: str) -> None:
    restore, auto_permission = recovery_start_options(app)
    reason_text = str(reason or '').strip()
    app.runtime_supervisor.start(
        agent_names=tuple(app.config.agents),
        restore=restore,
        auto_permission=auto_permission,
        cleanup_tmux_orphans=False,
        interactive_tmux_layout=True,
        recreate_namespace=not reason_text.startswith('pane_recovery:'),
        reflow_workspace=reason_text.startswith('pane_recovery:'),
        recreate_reason=reason_text,
        background_maintenance=True,
    )


__all__ = [
    'mount_agent_from_policy',
    'persist_start_policy',
    'recovery_start_options',
    'remount_project_from_policy',
]
