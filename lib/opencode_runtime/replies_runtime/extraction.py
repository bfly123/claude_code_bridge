from __future__ import annotations


def extract_text(parts: list[dict], allow_reasoning_fallback: bool = True) -> str:
    text = _collect_text(parts, {'text'})
    if text:
        return text
    if allow_reasoning_fallback:
        return _collect_text(parts, {'reasoning'})
    return ''


def extract_req_id_from_text(text: str, req_id_re) -> str | None:
    if not text:
        return None
    match = req_id_re.search(text)
    return match.group(1).lower() if match else None


def _collect_text(parts: list[dict], types: set[str]) -> str:
    out: list[str] = []
    for part in parts:
        if part.get('type') not in types:
            continue
        text = part.get('text')
        if isinstance(text, str) and text:
            out.append(text)
    return ''.join(out).strip()


__all__ = ['extract_req_id_from_text', 'extract_text']
