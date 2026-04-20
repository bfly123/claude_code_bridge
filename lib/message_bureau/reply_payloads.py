from __future__ import annotations

_REPLY_PREFIX = 'reply:'
_DELIVERY_PREFIX = 'delivery:'


def compose_reply_payload(reply_id: str, *, delivery_job_id: str | None = None) -> str:
    normalized_reply_id = str(reply_id or '').strip()
    if not normalized_reply_id:
        raise ValueError('reply_id cannot be empty')
    parts = [f'{_REPLY_PREFIX}{normalized_reply_id}']
    normalized_delivery_job_id = str(delivery_job_id or '').strip()
    if normalized_delivery_job_id:
        parts.append(f'{_DELIVERY_PREFIX}{normalized_delivery_job_id}')
    return ' '.join(parts)


def reply_id_from_payload(payload_ref: str | None) -> str | None:
    return _value_for_prefix(payload_ref, _REPLY_PREFIX)


def delivery_job_id_from_payload(payload_ref: str | None) -> str | None:
    return _value_for_prefix(payload_ref, _DELIVERY_PREFIX)


def _value_for_prefix(payload_ref: str | None, prefix: str) -> str | None:
    text = str(payload_ref or '').strip()
    if not text:
        return None
    for token in text.replace(';', ' ').split():
        if token.startswith(prefix):
            value = token[len(prefix) :].strip()
            return value or None
    return None


__all__ = [
    'compose_reply_payload',
    'delivery_job_id_from_payload',
    'reply_id_from_payload',
]
