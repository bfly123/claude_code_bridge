from __future__ import annotations

from pathlib import Path

from storage.json_store import JsonStore
from storage.paths import PathLayout

from .models import FaultRule, SCHEMA_VERSION


class FaultInjectionStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load_rules(self) -> tuple[FaultRule, ...]:
        path = self._layout.ccbd_fault_injection_path
        if not path.exists():
            return ()
        payload = self._store.load(path)
        if int(payload.get('schema_version') or 0) != SCHEMA_VERSION:
            raise ValueError(f'{path}: unsupported schema_version')
        rules = payload.get('rules') or ()
        return tuple(FaultRule.from_record(item) for item in rules if isinstance(item, dict))

    def save_rules(self, rules: tuple[FaultRule, ...]) -> None:
        path = self._layout.ccbd_fault_injection_path
        if not rules:
            try:
                path.unlink()
            except FileNotFoundError:
                return
            return
        self._store.save(
            path,
            {
                'schema_version': SCHEMA_VERSION,
                'record_type': 'fault_rule_set',
                'rules': [rule.to_record() for rule in rules],
            },
        )


__all__ = ['FaultInjectionStore']
