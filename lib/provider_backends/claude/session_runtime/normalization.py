from __future__ import annotations

import re


_SETTING_SOURCES_RE = re.compile(
    r"(?P<prefix>(?:^|[;\s])--setting-sources\s+)(?P<quote>['\"]?)project,local(?P=quote)(?=$|[\s;])"
)


def normalize_claude_start_cmd(value: str) -> tuple[str, bool]:
    raw = str(value or "").strip()
    if not raw:
        return raw, False
    if "user,project,local" in raw:
        return raw, False
    if "--setting-sources" not in raw or "project,local" not in raw:
        return raw, False

    normalized, count = _SETTING_SOURCES_RE.subn(
        lambda match: (
            f"{match.group('prefix')}{match.group('quote')}user,project,local{match.group('quote')}"
        ),
        raw,
        count=1,
    )
    return normalized, count > 0 and normalized != raw


def normalize_session_data(data: dict) -> bool:
    if not isinstance(data, dict):
        return False

    changed = False
    for key in ("claude_start_cmd", "start_cmd"):
        current = data.get(key)
        if not isinstance(current, str):
            continue
        normalized, updated = normalize_claude_start_cmd(current)
        if updated:
            data[key] = normalized
            changed = True
    return changed


__all__ = [
    "normalize_claude_start_cmd",
    "normalize_session_data",
]
