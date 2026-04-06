from __future__ import annotations

from pathlib import Path

from storage.json_store import JsonStore
from storage.paths import PathLayout

from .state_models import PersistedExecutionState


class ExecutionStateStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self, job_id: str) -> PersistedExecutionState | None:
        path = self._layout.execution_state_path(job_id)
        if not path.exists():
            return None
        return self._store.load(path, loader=PersistedExecutionState.from_record)

    def save(self, state: PersistedExecutionState) -> None:
        path = self._layout.execution_state_path(state.job_id)
        self._store.save(path, state, serializer=lambda value: value.to_record())

    def remove(self, job_id: str) -> None:
        path = self._layout.execution_state_path(job_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return

    def list_all(self) -> list[PersistedExecutionState]:
        directory = self._layout.ccbd_executions_dir
        if not directory.exists():
            return []
        return _load_state_files(directory, self._store)

    def summary(self) -> dict[str, object]:
        return _summary_from_states(self.list_all())


def _load_state_files(directory: Path, store: JsonStore) -> list[PersistedExecutionState]:
    states: list[PersistedExecutionState] = []
    for path in sorted(directory.glob('*.json')):
        try:
            states.append(store.load(path, loader=PersistedExecutionState.from_record))
        except Exception:
            continue
    return states


def _summary_from_states(states: list[PersistedExecutionState]) -> dict[str, object]:
    recoverable = [state for state in states if state.resume_capable]
    nonrecoverable = [state for state in states if not state.resume_capable]
    return {
        'active_execution_count': len(states),
        'recoverable_execution_count': len(recoverable),
        'nonrecoverable_execution_count': len(nonrecoverable),
        'pending_items_count': sum(1 for state in states if state.pending_items),
        'terminal_pending_count': sum(1 for state in states if state.pending_decision is not None),
        'recoverable_execution_providers': sorted({state.provider for state in recoverable}),
        'nonrecoverable_execution_providers': sorted({state.provider for state in nonrecoverable}),
    }
