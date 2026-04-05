from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional


def _normalize_path_for_match(value: str) -> str:
    s = (value or "").strip()
    if os.name == "nt":
        if len(s) >= 4 and s[0] == "/" and s[2] == "/" and s[1].isalpha():
            s = f"{s[1].lower()}:/{s[3:]}"
        if s.startswith("/mnt/") and len(s) > 6:
            drive = s[5]
            if drive.isalpha() and s[6:7] == "/":
                s = f"{drive.lower()}:/{s[7:]}"
    try:
        path = Path(s).expanduser()
        normalized = str(path.absolute())
    except Exception:
        normalized = str(value or "")
    normalized = normalized.replace("\\", "/").rstrip("/")
    if os.name == "nt":
        normalized = normalized.lower()
    return normalized


def path_is_same_or_parent(parent: str, child: str) -> bool:
    parent_norm = _normalize_path_for_match(parent)
    child_norm = _normalize_path_for_match(child)
    if not parent_norm or not child_norm:
        return False
    if parent_norm == child_norm:
        return True
    if not child_norm.startswith(parent_norm):
        return False
    return child_norm == parent_norm or child_norm[len(parent_norm) :].startswith("/")


def read_droid_session_start(session_path: Path, *, max_lines: int = 30) -> tuple[Optional[str], Optional[str]]:
    try:
        with session_path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(max_lines):
                line = handle.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if not isinstance(entry, dict) or entry.get("type") != "session_start":
                    continue
                cwd = entry.get("cwd")
                sid = entry.get("id")
                cwd_str = str(cwd).strip() if isinstance(cwd, str) else None
                sid_str = str(sid).strip() if isinstance(sid, str) else None
                return cwd_str or None, sid_str or None
    except OSError:
        return None, None
    return None, None


def _extract_content_text(content: Any) -> Optional[str]:
    if content is None:
        return None
    if isinstance(content, str):
        return content.strip() or None
    if not isinstance(content, list):
        return None
    texts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip().lower()
        if item_type in ("thinking", "thinking_delta"):
            continue
        text = item.get("text")
        if not text and item_type == "text":
            text = item.get("content")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    if not texts:
        return None
    return "\n".join(texts).strip()


def extract_message(entry: dict, role: str) -> Optional[str]:
    if not isinstance(entry, dict):
        return None
    entry_type = str(entry.get("type") or "").strip().lower()
    if entry_type == "message":
        message = entry.get("message")
        if isinstance(message, dict):
            msg_role = str(message.get("role") or "").strip().lower()
            if msg_role == role:
                return _extract_content_text(message.get("content"))
    msg_role = str(entry.get("role") or entry_type).strip().lower()
    if msg_role == role:
        return _extract_content_text(entry.get("content") or entry.get("message"))
    return None
