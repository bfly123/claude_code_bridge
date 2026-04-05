from __future__ import annotations

import os
from pathlib import Path
import posixpath
import re

_WIN_DRIVE_RE = re.compile(r"^[A-Za-z]:([/\\\\]|$)")
_MNT_DRIVE_RE = re.compile(r"^/mnt/([A-Za-z])/(.*)$")
_MSYS_DRIVE_RE = re.compile(r"^/([A-Za-z])/(.*)$")


def _looks_like_windows_path(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if _WIN_DRIVE_RE.match(text):
        return True
    if text.startswith("\\\\") or text.startswith("//"):
        return True
    return False


def normalize_path_for_match(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""

    if text.startswith("~"):
        try:
            text = os.path.expanduser(text)
        except Exception:
            pass

    try:
        preview = text.replace("\\", "/")
        is_abs = (
            preview.startswith("/")
            or preview.startswith("//")
            or bool(_WIN_DRIVE_RE.match(preview))
            or preview.startswith("\\\\")
        )
        if not is_abs:
            text = str((Path.cwd() / Path(text)).absolute())
    except Exception:
        pass

    text = text.replace("\\", "/")

    match = _MNT_DRIVE_RE.match(text)
    if match:
        drive = match.group(1).lower()
        rest = match.group(2)
        text = f"{drive}:/{rest}"
    else:
        match = _MSYS_DRIVE_RE.match(text)
        if match and ("MSYSTEM" in os.environ or os.name == "nt"):
            drive = match.group(1).lower()
            rest = match.group(2)
            text = f"{drive}:/{rest}"

    if text.startswith("//"):
        prefix = "//"
        rest = text[2:]
        rest = posixpath.normpath(rest)
        text = prefix + rest.lstrip("/")
    else:
        text = posixpath.normpath(text)

    if _WIN_DRIVE_RE.match(text):
        text = text[0].lower() + text[1:]

    if len(text) > 1 and text.endswith("/"):
        text = text.rstrip("/")
        if _WIN_DRIVE_RE.match(text) and not text.endswith("/"):
            if len(text) == 2:
                text = text + "/"

    if _looks_like_windows_path(text):
        text = text.casefold()

    return text


def work_dir_match_keys(work_dir: Path) -> set[str]:
    keys: set[str] = set()
    candidates: list[str] = []
    for raw in (os.environ.get("PWD"), str(work_dir)):
        if raw:
            candidates.append(raw)
    try:
        candidates.append(str(work_dir.resolve()))
    except Exception:
        pass
    for candidate in candidates:
        normalized = normalize_path_for_match(candidate)
        if normalized:
            keys.add(normalized)
    return keys


def normpath_within(child_norm: str, parent_norm: str) -> bool:
    if not child_norm or not parent_norm:
        return False
    if child_norm == parent_norm:
        return True
    prefix = parent_norm if parent_norm.endswith("/") else (parent_norm + "/")
    return child_norm.startswith(prefix)


def extract_session_work_dir_norm(session_data: dict) -> str:
    if not isinstance(session_data, dict):
        return ""
    raw_norm = session_data.get("work_dir_norm")
    if isinstance(raw_norm, str) and raw_norm.strip():
        return normalize_path_for_match(raw_norm)
    raw = session_data.get("work_dir")
    if isinstance(raw, str) and raw.strip():
        return normalize_path_for_match(raw)
    return ""
