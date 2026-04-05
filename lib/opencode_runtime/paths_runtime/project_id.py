from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from provider_core.protocol import REQ_ID_PREFIX

# Match both old (32-char hex) and new (YYYYMMDD-HHMMSS-mmm-PID-counter) req_id formats
REQ_ID_RE = re.compile(rf"{re.escape(REQ_ID_PREFIX)}\s*([0-9a-fA-F]{{32}}|\d{{8}}-\d{{6}}-\d{{3}}-\d+-\d+)")


def compute_opencode_project_id(work_dir: Path) -> str:
    """
    Compute OpenCode projectID for a directory.

    OpenCode's current behavior (for git worktrees) uses the lexicographically smallest
    root commit hash from `git rev-list --max-parents=0 --all` as the projectID.
    Non-git directories fall back to "global".
    """
    try:
        cwd = Path(work_dir).expanduser()
    except Exception:
        cwd = Path.cwd()

    git_root, git_dir = _find_git_dir(cwd)
    cached = _read_cached_project_id(git_dir)
    if cached:
        return cached

    try:
        import subprocess

        if not shutil.which("git"):
            return "global"

        kwargs = {
            "cwd": str(git_root or cwd),
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "stdout": subprocess.PIPE,
            "stderr": subprocess.DEVNULL,
            "check": False,
        }
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = startupinfo
        proc = subprocess.run(["git", "rev-list", "--max-parents=0", "--all"], **kwargs)
        roots = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
        roots.sort()
        return roots[0] if roots else "global"
    except Exception:
        return "global"


def _find_git_dir(start: Path) -> tuple[Path | None, Path | None]:
    for candidate in [start, *start.parents]:
        git_entry = candidate / ".git"
        if not git_entry.exists():
            continue
        if git_entry.is_dir():
            return candidate, git_entry
        if git_entry.is_file():
            try:
                raw = git_entry.read_text(encoding="utf-8", errors="replace").strip()
                prefix = "gitdir:"
                if raw.lower().startswith(prefix):
                    gitdir = raw[len(prefix) :].strip()
                    gitdir_path = Path(gitdir)
                    if not gitdir_path.is_absolute():
                        gitdir_path = (candidate / gitdir_path).resolve()
                    return candidate, gitdir_path
            except Exception:
                continue
    return None, None


def _read_cached_project_id(git_dir: Path | None) -> str | None:
    if not git_dir:
        return None
    try:
        cache_path = git_dir / "opencode"
        if not cache_path.exists():
            return None
        cached = cache_path.read_text(encoding="utf-8", errors="replace").strip()
        return cached or None
    except Exception:
        return None


__all__ = ["REQ_ID_RE", "compute_opencode_project_id"]
