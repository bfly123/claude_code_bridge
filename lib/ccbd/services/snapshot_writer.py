from __future__ import annotations

from ccbd.system import utc_now
from completion.models import CompletionDecision, CompletionFamily, CompletionSnapshot, CompletionState
from completion.snapshot_store import CompletionSnapshotStore
from storage.paths import PathLayout


class SnapshotWriter:
    def __init__(
        self,
        layout: PathLayout,
        store: CompletionSnapshotStore | None = None,
        *,
        clock=utc_now,
        preview_limit: int = 240,
    ) -> None:
        self._layout = layout
        self._store = store or CompletionSnapshotStore(layout)
        self._clock = clock
        self._preview_limit = preview_limit

    def load(self, job_id: str) -> CompletionSnapshot | None:
        return self._store.load(job_id)

    def write_completion(
        self,
        *,
        job_id: str,
        agent_name: str,
        profile_family: CompletionFamily,
        state: CompletionState,
        decision: CompletionDecision,
        updated_at: str | None = None,
        reply_preview: str | None = None,
    ) -> CompletionSnapshot:
        timestamp = updated_at or self._clock()
        preview = reply_preview if reply_preview is not None else self._preview(decision.reply)
        snapshot = CompletionSnapshot(
            job_id=job_id,
            agent_name=agent_name,
            profile_family=profile_family,
            state=state,
            latest_decision=decision,
            latest_reply_preview=preview,
            updated_at=timestamp,
        )
        self._store.save(snapshot)
        return snapshot

    def write_pending(self, *, job_id: str, agent_name: str, profile_family: CompletionFamily) -> CompletionSnapshot:
        state = CompletionState(terminal=False)
        return self.write_completion(
            job_id=job_id,
            agent_name=agent_name,
            profile_family=profile_family,
            state=state,
            decision=CompletionDecision.pending(),
        )

    def _preview(self, reply: str) -> str:
        text = (reply or '').strip()
        if len(text) <= self._preview_limit:
            return text
        return text[: self._preview_limit].rstrip() + '...'


__all__ = ['SnapshotWriter']
