from __future__ import annotations

import os
from pathlib import Path

from agents.models import AgentSpec
from provider_backends.gemini.comm_runtime.project_hash import project_hash_candidates
from provider_backends.runtime_restore import ProviderRestoreTarget, resolve_restore_context


def resolve_gemini_restore_target(
    *,
    spec: AgentSpec,
    runtime_dir: Path,
    restore: bool,
    workspace_path: Path | None = None,
    load_project_session_fn,
) -> ProviderRestoreTarget:
    context = resolve_restore_context(
        runtime_dir,
        provider="gemini",
        agent_name=spec.name,
        workspace_path=workspace_path,
    )
    default_target = ProviderRestoreTarget(run_cwd=context.workspace_path, has_history=False)
    if not restore:
        return default_target

    session = load_project_session_fn(context.workspace_path, instance=context.session_instance)
    if session is not None:
        session_cwd = existing_dir(getattr(session, "work_dir", ""))
        if session_cwd is not None and gemini_has_history(session_cwd):
            return ProviderRestoreTarget(run_cwd=session_cwd, has_history=True)

    for candidate in candidate_dirs(context.workspace_path, context.project_root):
        if gemini_has_history(candidate):
            return ProviderRestoreTarget(run_cwd=candidate, has_history=True)
    return default_target


def candidate_dirs(workspace_path: Path, project_root: Path | None) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()

    def add_candidate(value: Path | None) -> None:
        if value is None:
            return
        try:
            path = value.expanduser()
        except Exception:
            return
        if path in seen or not path.is_dir():
            return
        seen.add(path)
        candidates.append(path)

    add_candidate(workspace_path)
    add_candidate(project_root)
    env_pwd = str(os.environ.get("PWD") or "").strip()
    if env_pwd:
        add_candidate(Path(env_pwd))
    return candidates


def gemini_has_history(work_dir: Path) -> bool:
    gemini_root = gemini_root_dir()
    if not gemini_root.is_dir():
        return False
    for project_hash in project_hash_candidates(work_dir, root=gemini_root):
        chats_dir = gemini_root / project_hash / "chats"
        if chats_dir.is_dir() and any(chats_dir.glob("session-*.json")):
            return True
    return False


def existing_dir(value: object) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        path = Path(raw).expanduser()
    except Exception:
        return None
    return path if path.is_dir() else None


def gemini_root_dir() -> Path:
    raw = os.environ.get("GEMINI_ROOT") or (Path.home() / ".gemini" / "tmp")
    return Path(raw).expanduser()


__all__ = [
    "candidate_dirs",
    "existing_dir",
    "gemini_has_history",
    "gemini_root_dir",
    "resolve_gemini_restore_target",
]
