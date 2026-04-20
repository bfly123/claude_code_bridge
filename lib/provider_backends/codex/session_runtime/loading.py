from __future__ import annotations

from pathlib import Path
import shutil

from provider_backends.pane_log_support.session import compute_session_key_for_provider

from .model import CodexProjectSession
from .pathing import find_project_session_file, read_json, write_back
from .follow_policy import codex_home_path, codex_session_root_path


def load_project_session(work_dir: Path, instance: str | None = None) -> CodexProjectSession | None:
    session_file = find_project_session_file(work_dir, instance)
    if not session_file:
        return None
    data = read_json(session_file)
    if not data:
        return None
    updated = _migrate_legacy_codex_layout(data)
    session = CodexProjectSession(session_file=session_file, data=data)
    if updated:
        write_back(session)
    return session


def compute_session_key(session: CodexProjectSession, instance: str | None = None) -> str:
    return compute_session_key_for_provider(session, provider="codex", instance=instance)


def _migrate_legacy_codex_layout(data: dict[str, object]) -> bool:
    session_root = codex_session_root_path(data)
    if session_root is None:
        return False
    codex_home = codex_home_path(data)
    target_home = _home_for_session_root(session_root)
    target_root = target_home / "sessions"
    _migrate_root_tree(session_root, target_root)
    updated = False
    if codex_home is None or codex_home != target_home:
        data["codex_home"] = str(target_home)
        updated = True
    if session_root != target_root:
        data["codex_session_root"] = str(target_root)
        updated = True
    session_path = _normalize_path(data.get("codex_session_path"))
    if session_path is not None:
        migrated_session_path = _migrated_log_path(session_path, session_root=session_root, target_root=target_root)
        if migrated_session_path is not None and migrated_session_path != session_path:
            data["codex_session_path"] = str(migrated_session_path)
            updated = True
    return updated


def _home_for_session_root(session_root: Path) -> Path:
    normalized_root = Path(session_root).expanduser()
    if normalized_root.name == "sessions":
        parent = normalized_root.parent
        if parent.name == "home":
            return parent
        return parent / "home"
    return normalized_root / "home"


def _migrate_root_tree(session_root: Path, target_root: Path) -> None:
    normalized_source = _normalize_path(session_root)
    normalized_target = _normalize_path(target_root)
    if normalized_source is None or normalized_target is None:
        return
    if normalized_source == normalized_target:
        normalized_target.mkdir(parents=True, exist_ok=True)
        return
    if normalized_source.name != "sessions":
        normalized_target.mkdir(parents=True, exist_ok=True)
        return
    if normalized_target.exists():
        return
    normalized_target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(normalized_source), str(normalized_target))
    except Exception:
        normalized_target.mkdir(parents=True, exist_ok=True)


def _migrated_log_path(session_path: Path, *, session_root: Path, target_root: Path) -> Path | None:
    normalized_session = _normalize_path(session_path)
    normalized_root = _normalize_path(session_root)
    normalized_target = _normalize_path(target_root)
    if normalized_session is None or normalized_root is None or normalized_target is None:
        return None
    try:
        relative = normalized_session.relative_to(normalized_root)
    except Exception:
        return None
    return normalized_target / relative


def _normalize_path(value: object) -> Path | None:
    if value is None:
        return None
    try:
        return Path(value).expanduser().resolve()
    except Exception:
        try:
            return Path(value).expanduser()
        except Exception:
            return None


__all__ = ["compute_session_key", "load_project_session"]
