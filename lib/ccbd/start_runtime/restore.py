from __future__ import annotations

from agents.models import AgentRestoreState, RestoreMode, RestoreStatus


def build_restore_state(mode: str) -> AgentRestoreState:
    status_map = {
        'fresh': RestoreStatus.FRESH,
        'provider': RestoreStatus.PROVIDER,
        'auto': RestoreStatus.CHECKPOINT,
        'attach': RestoreStatus.CHECKPOINT,
        'memory': RestoreStatus.CHECKPOINT,
    }
    restore_mode = RestoreMode.AUTO if mode == 'auto' else RestoreMode.FRESH if mode == 'fresh' else RestoreMode.PROVIDER if mode == 'provider' else RestoreMode.AUTO
    return AgentRestoreState(
        restore_mode=restore_mode,
        last_checkpoint=None,
        conversation_summary='bootstrap placeholder',
        open_tasks=[],
        files_touched=[],
        base_commit=None,
        head_commit=None,
        last_restore_status=status_map.get(mode, RestoreStatus.CHECKPOINT),
    )
