from __future__ import annotations

from dataclasses import dataclass

from cli.services.tmux_project_cleanup import ProjectTmuxCleanupSummary


@dataclass(frozen=True)
class StopAllSummary:
    project_id: str
    state: str
    socket_path: str
    forced: bool
    stopped_agents: tuple[str, ...] = ()
    cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            'project_id': self.project_id,
            'state': self.state,
            'socket_path': self.socket_path,
            'forced': self.forced,
            'stopped_agents': list(self.stopped_agents),
            'cleanup_summaries': [
                {
                    'socket_name': item.socket_name,
                    'owned_panes': list(item.owned_panes),
                    'active_panes': list(item.active_panes),
                    'orphaned_panes': list(item.orphaned_panes),
                    'killed_panes': list(item.killed_panes),
                }
                for item in self.cleanup_summaries
            ],
        }


@dataclass(frozen=True)
class StopAllExecution:
    summary: StopAllSummary
    stopped_agents: tuple[str, ...]
    actions_taken: tuple[str, ...]
    cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...]


__all__ = ['StopAllExecution', 'StopAllSummary']
