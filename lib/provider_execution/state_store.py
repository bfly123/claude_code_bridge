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
        self._store.save(self._layout.execution_state_path(state.job_id), state, serializer=lambda value: value.to_record())

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
        states: list[PersistedExecutionState] = []
        for path in sorted(directory.glob('*.json')):
            try:
                states.append(self._store.load(path, loader=PersistedExecutionState.from_record))
            except Exception:
                continue
        return states

    def summary(self) -> dict[str, object]:
        states = self.list_all()
        recoverable_providers = sorted({state.provider for state in states if state.resume_capable})
        nonrecoverable_providers = sorted({state.provider for state in states if not state.resume_capable})
        return {
            'active_execution_count': len(states),
            'recoverable_execution_count': sum(1 for state in states if state.resume_capable),
            'nonrecoverable_execution_count': sum(1 for state in states if not state.resume_capable),
            'pending_items_count': sum(1 for state in states if state.pending_items),
            'terminal_pending_count': sum(1 for state in states if state.pending_decision is not None),
            'recoverable_execution_providers': recoverable_providers,
            'nonrecoverable_execution_providers': nonrecoverable_providers,
        }
