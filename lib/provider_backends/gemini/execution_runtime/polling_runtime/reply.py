from __future__ import annotations


def clean_reply(
    reply: str,
    *,
    req_id: str,
    extract_reply_for_req_fn,
    is_done_text_fn,
    strip_done_text_fn,
) -> str:
    if req_id and is_done_text_fn(reply, req_id):
        extracted = extract_reply_for_req_fn(reply, req_id)
        if extracted.strip():
            return extracted.strip()
    cleaned = strip_done_text_fn(reply, req_id) if req_id else reply
    return cleaned.strip() if cleaned else ''


def int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


__all__ = ['clean_reply', 'int_or_none']
