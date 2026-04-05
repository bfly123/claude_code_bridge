from __future__ import annotations

import hashlib
import os
import posixpath
import re
from pathlib import Path

from project.discovery import find_nearest_project_anchor, find_workspace_binding, load_workspace_binding
from project.ids import compute_project_id


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

    # Expand "~" early.
    if raw.startswith("~"):
        try:
            raw = os.path.expanduser(raw)
        except Exception:
            pass

    # Absolutize when relative (best-effort).
    try:
        preview = raw.replace("\\", "/")
        is_abs = (
            preview.startswith("/")
            or preview.startswith("//")
            or preview.startswith("\\\\")
            or bool(_WIN_DRIVE_RE.match(preview))
        )
        if not is_abs:
            raw = str((Path.cwd() / Path(raw)).absolute())
    except Exception:
        pass

    s = raw.replace("\\", "/")

    # Map WSL mount paths to a Windows-like drive form for stable matching.
    m = _MNT_DRIVE_RE.match(s)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2)
        s = f"{drive}:/{rest}"
    else:
        # Map MSYS /c/... to c:/...
        m = _MSYS_DRIVE_RE.match(s)
        if m and ("MSYSTEM" in os.environ or os.name == "nt"):
            drive = m.group(1).lower()
            rest = m.group(2)
            s = f"{drive}:/{rest}"

    # Collapse redundant separators and dot segments using POSIX semantics (we forced "/").
    if s.startswith("//"):
        prefix = "//"
        rest = posixpath.normpath(s[2:])
        s = prefix + rest.lstrip("/")
    else:
        s = posixpath.normpath(s)

    # Normalize Windows drive letter casing.
    if _WIN_DRIVE_RE.match(s):
        s = s[0].lower() + s[1:]

    return s


def resolve_project_root(work_dir: Path | str) -> Path:
    try:
        current = Path(work_dir).expanduser().resolve()
    except Exception:
        current = Path(work_dir).expanduser().absolute()

    binding_path = find_workspace_binding(current)
    if binding_path is not None:
        binding = load_workspace_binding(binding_path)
        target_project = Path(str(binding['target_project'])).expanduser()
        try:
            return target_project.resolve()
        except Exception:
            return target_project.absolute()

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
