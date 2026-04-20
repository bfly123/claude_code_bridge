from __future__ import annotations

from pathlib import Path

from provider_runtime import (
    ProgressState,
    ProviderCompletionState,
    ProviderHealthSnapshot,
    ProviderHealthSnapshotStore,
)
from storage.paths import PathLayout


def test_provider_health_snapshot_store_tracks_job_history(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    store = ProviderHealthSnapshotStore(layout)

    store.append(
        ProviderHealthSnapshot(
            job_id='job-1',
            provider='codex',
            agent_name='Agent1',
            runtime_alive=True,
            session_reachable=True,
            progress_state=ProgressState.ACCEPTED,
            completion_state=ProviderCompletionState.NOT_COMPLETE,
            last_progress_at='2026-03-30T12:00:00Z',
            observed_at='2026-03-30T12:00:00Z',
            diagnostics={'phase': 'accepted'},
        )
    )
    store.append(
        ProviderHealthSnapshot(
            job_id='job-1',
            provider='codex',
            agent_name='agent1',
            runtime_alive=True,
            session_reachable=True,
            progress_state=ProgressState.OUTPUT_ADVANCING,
            completion_state=ProviderCompletionState.TERMINAL_COMPLETE,
            last_progress_at='2026-03-30T12:00:03Z',
            observed_at='2026-03-30T12:00:05Z',
            diagnostics={'phase': 'complete'},
        )
    )

    latest = store.latest('job-1')
    assert latest is not None
    assert latest.agent_name == 'agent1'
    assert latest.progress_state is ProgressState.OUTPUT_ADVANCING
    assert latest.completion_state is ProviderCompletionState.TERMINAL_COMPLETE
    assert len(store.list_job('job-1')) == 2
    assert len(store.list_all()) == 2
