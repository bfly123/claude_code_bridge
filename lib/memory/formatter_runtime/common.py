from __future__ import annotations

from datetime import datetime


_PROVIDER_LABELS = {
    'auto': 'Auto',
    'claude': 'Claude',
    'codex': 'Codex',
    'droid': 'Droid',
    'gemini': 'Gemini',
    'opencode': 'OpenCode',
}


def provider_label(provider: str | None) -> str:
    key = str(provider or 'claude').strip().lower()
    if key in _PROVIDER_LABELS:
        return _PROVIDER_LABELS[key]
    return str(provider).strip().title() if provider else 'Claude'


def transfer_timestamp(*, now_fn=datetime.now) -> datetime:
    return now_fn()


__all__ = ['provider_label', 'transfer_timestamp']
