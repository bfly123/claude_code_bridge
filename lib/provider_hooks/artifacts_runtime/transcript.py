from __future__ import annotations

from pathlib import Path
import re

from provider_core.protocol import ANY_REQ_ID_PATTERN, REQ_ID_BOUNDARY_PATTERN

REQ_ID_RE = re.compile(rf'CCB_REQ_ID:\s*({ANY_REQ_ID_PATTERN}){REQ_ID_BOUNDARY_PATTERN}', re.IGNORECASE)


def extract_req_id(text: str) -> str | None:
    match = REQ_ID_RE.search(str(text or ''))
    if not match:
        return None
    return str(match.group(1) or '').strip() or None


def latest_req_id_from_transcript(transcript_path: str | Path | None) -> str | None:
    raw = str(transcript_path or '').strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return None
    matches = REQ_ID_RE.findall(content)
    if not matches:
        return None
    return str(matches[-1] or '').strip() or None


__all__ = ['extract_req_id', 'latest_req_id_from_transcript']
