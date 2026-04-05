from __future__ import annotations

import hashlib
import os
import posixpath
import re
from pathlib import Path

_WIN_DRIVE_RE = re.compile(r'^[A-Za-z]:([/\\]|$)')
_MNT_DRIVE_RE = re.compile(r'^/mnt/([A-Za-z])/(.*)$')


def normalize_project_path(value: str | Path) -> str:
    raw = str(value).strip()
    if not raw:
        return ''
    if raw.startswith('~'):
        raw = os.path.expanduser(raw)
    path = Path(raw)
    try:
        if path.exists():
            raw = str(path.resolve())
        else:
            raw = str(path.absolute())
    except Exception:
        raw = str(path)
    normalized = raw.replace('\\', '/')
    match = _MNT_DRIVE_RE.match(normalized)
    if match:
        normalized = f"{match.group(1).lower()}:/{match.group(2)}"
    normalized = posixpath.normpath(normalized)
    if _WIN_DRIVE_RE.match(normalized):
        normalized = normalized[0].lower() + normalized[1:]
        normalized = normalized.casefold()
    return normalized


def compute_project_id(project_root: Path) -> str:
    normalized = normalize_project_path(project_root)
    if not normalized:
        raise ValueError('project_root cannot be empty')
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def project_slug(project_root: Path) -> str:
    normalized = normalize_project_path(project_root)
    digest = compute_project_id(project_root)[:8]
    base_name = Path(normalized).name or 'project'
    slug = re.sub(r'[^a-z0-9._-]+', '-', base_name.lower()).strip('-') or 'project'
    return f'{slug}-{digest}'
