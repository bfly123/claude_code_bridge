from __future__ import annotations

from ccbd.models import CcbdRestoreReport


def build_last_restore_report(dispatcher, *, project_id: str) -> CcbdRestoreReport:
    entries = dispatcher._last_restore_entries
    return CcbdRestoreReport(
        project_id=project_id,
        generated_at=dispatcher._last_restore_generated_at or dispatcher._clock(),
        running_job_count=len(entries),
        restored_execution_count=sum(1 for entry in entries if entry.status in {'restored', 'replay_pending'}),
        replay_pending_count=sum(1 for entry in entries if entry.status == 'replay_pending'),
        terminal_pending_count=sum(1 for entry in entries if entry.status == 'terminal_pending'),
        abandoned_execution_count=sum(1 for entry in entries if entry.status == 'abandoned'),
        already_active_count=sum(1 for entry in entries if entry.status == 'already_active'),
        entries=entries,
    )


__all__ = ["build_last_restore_report"]
