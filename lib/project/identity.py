from __future__ import annotations

import hashlib
import os
import posixpath
import re
from pathlib import Path

from .discovery import find_nearest_project_anchor, find_workspace_binding, load_workspace_binding
from .ids import compute_project_id


_WIN_DRIVE_RE = re.compile(r"^[A-Za-z]:([/\\\\]|$)")
_MNT_DRIVE_RE = re.compile(r"^/mnt/([A-Za-z])/(.*)$")
_MSYS_DRIVE_RE = re.compile(r"^/([A-Za-z])/(.*)$")


def normalize_work_dir(value: str | Path) -> str:
    """
    Normalize a work_dir into a stable string for hashing and matching.

    Goals:
    - Be stable within a single environment (Linux/WSL/Windows/MSYS).
    - Reduce trivial path-format mismatches (slashes, drive letter casing, /mnt/<drive> mapping).
    - Avoid resolve() by default to reduce symlink/interop surprises.
    """
    raw = str(value).strip()
    if not raw:
        return ""

    raw = _expand_user_path(raw)
    raw = _absolutize_relative_path(raw)
    normalized = _normalize_path_slashes(raw)
    normalized = _normalize_platform_drive_mapping(normalized)
    normalized = _normalize_posix_segments(normalized)
    return _normalize_drive_letter_case(normalized)


def resolve_project_root(work_dir: Path | str) -> Path:
    current = _resolved_path(work_dir)

    binding_path = find_workspace_binding(current)
    if binding_path is not None:
        binding = load_workspace_binding(binding_path)
        return _resolved_path(binding['target_project'])

    anchor = find_nearest_project_anchor(current)
    if anchor is not None:
        return anchor
    return current


def compute_ccb_project_id(work_dir: Path) -> str:
    """
    Compatibility wrapper for the v2 project id.

    Project identity is rooted at the resolved project root:
    - workspace binding target project
    - nearest ancestor/current `.ccb` anchor
    - current work_dir only when no project context exists
    """
    return compute_project_id(resolve_project_root(work_dir))


def compute_worktree_scope_id(work_dir: Path | str) -> str:
    """
    Compute a stable worktree/workspace scope id.

    Unlike ``compute_ccb_project_id``, this always hashes the resolved work_dir
    itself so different agent worktrees in the same project do not collapse to
    the same routing key.
    """
    norm = normalize_work_dir(work_dir)
    if not norm:
        return ""
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]


def _expand_user_path(raw: str) -> str:
    if raw.startswith("~"):
        try:
            return os.path.expanduser(raw)
        except Exception:
            return raw
    return raw


def _absolutize_relative_path(raw: str) -> str:
    try:
        if not _is_absolute_preview(raw):
            return str((Path.cwd() / Path(raw)).absolute())
    except Exception:
        return raw
    return raw


def _is_absolute_preview(raw: str) -> bool:
    preview = raw.replace("\\", "/")
    return (
        preview.startswith("/")
        or preview.startswith("//")
        or preview.startswith("\\\\")
        or bool(_WIN_DRIVE_RE.match(preview))
    )


def _normalize_path_slashes(raw: str) -> str:
    return raw.replace("\\", "/")


def _normalize_platform_drive_mapping(value: str) -> str:
    mount_match = _MNT_DRIVE_RE.match(value)
    if mount_match:
        drive = mount_match.group(1).lower()
        rest = mount_match.group(2)
        return f"{drive}:/{rest}"

    msys_match = _MSYS_DRIVE_RE.match(value)
    if msys_match and ("MSYSTEM" in os.environ or os.name == "nt"):
        drive = msys_match.group(1).lower()
        rest = msys_match.group(2)
        return f"{drive}:/{rest}"
    return value


def _normalize_posix_segments(value: str) -> str:
    if value.startswith("//"):
        prefix = "//"
        rest = posixpath.normpath(value[2:])
        return prefix + rest.lstrip("/")
    return posixpath.normpath(value)


def _normalize_drive_letter_case(value: str) -> str:
    if _WIN_DRIVE_RE.match(value):
        return value[0].lower() + value[1:]
    return value


def _resolved_path(path: Path | str) -> Path:
    current = Path(path).expanduser()
    try:
        return current.resolve()
    except Exception:
        return current.absolute()


__all__ = [
    'compute_ccb_project_id',
    'compute_worktree_scope_id',
    'normalize_work_dir',
    'resolve_project_root',
]
