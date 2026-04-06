from __future__ import annotations

import shutil
from pathlib import Path

from .git import apply_windows_process_options, find_git_dir, git_root_commit_cwd, read_cached_project_id


def compute_opencode_project_id(work_dir: Path) -> str:
    cwd = normalize_work_dir(work_dir)
    git_root, git_dir = find_git_dir(cwd)
    cached = read_cached_project_id(git_dir)
    if cached:
        return cached
    return root_commit_project_id(git_root=git_root, cwd=cwd)


def normalize_work_dir(work_dir: Path) -> Path:
    try:
        return Path(work_dir).expanduser()
    except Exception:
        return Path.cwd()


def root_commit_project_id(*, git_root: Path | None, cwd: Path) -> str:
    try:
        import subprocess

        if not shutil.which("git"):
            return "global"
        kwargs = subprocess_run_kwargs(git_root=git_root, cwd=cwd)
        proc = subprocess.run(["git", "rev-list", "--max-parents=0", "--all"], **kwargs)
        roots = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
        roots.sort()
        return roots[0] if roots else "global"
    except Exception:
        return "global"


def subprocess_run_kwargs(*, git_root: Path | None, cwd: Path) -> dict[str, object]:
    import subprocess

    kwargs: dict[str, object] = {
        "cwd": git_root_commit_cwd(git_root, cwd),
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "stdout": subprocess.PIPE,
        "stderr": subprocess.DEVNULL,
        "check": False,
    }
    apply_windows_process_options(kwargs)
    return kwargs


__all__ = [
    'compute_opencode_project_id',
    'normalize_work_dir',
    'root_commit_project_id',
    'subprocess_run_kwargs',
]
