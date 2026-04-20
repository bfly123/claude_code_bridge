from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .normalization import compute_project_hashes


def project_hash_candidates(work_dir: Optional[Path] = None, *, root: Optional[Path] = None) -> list[str]:
    abs_path = resolved_work_dir(work_dir)
    raw_base, slug_base, sha256_hash = candidate_bases(abs_path)
    discovered = discover_project_hashes(
        root=root,
        raw_base=raw_base,
        slug_base=slug_base,
        suffix_re=suffix_pattern(slug_base),
    )
    return ordered_candidates(discovered, slug_base=slug_base, raw_base=raw_base, sha256_hash=sha256_hash)


def get_project_hash(work_dir: Optional[Path] = None, *, root: Path) -> str:
    path = work_dir or Path.cwd()
    root_path = Path(root).expanduser()
    candidates = project_hash_candidates(path, root=root_path)
    for project_hash in candidates:
        if (root_path / project_hash / "chats").is_dir():
            return project_hash
    return candidates[0] if candidates else ""


def resolved_work_dir(work_dir: Optional[Path]) -> Path:
    path = work_dir or Path.cwd()
    try:
        return path.expanduser().absolute()
    except Exception:
        return path


def candidate_bases(path: Path) -> tuple[str, str, str]:
    raw_base = (path.name or "").strip()
    slug_base, sha256_hash = compute_project_hashes(path)
    return raw_base, slug_base, sha256_hash


def suffix_pattern(slug_base: str):
    if not slug_base:
        return None
    return re.compile(rf"^{re.escape(slug_base)}-\d+$")


def discover_project_hashes(
    *,
    root: Optional[Path],
    raw_base: str,
    slug_base: str,
    suffix_re,
) -> list[tuple[float, str]]:
    root_path = Path(root).expanduser() if root else None
    if root_path is None or not root_path.is_dir() or not slug_base:
        return []
    discovered: list[tuple[float, str]] = []
    try:
        for child in root_path.iterdir():
            candidate = discovered_project_hash(child, raw_base=raw_base, slug_base=slug_base, suffix_re=suffix_re)
            if candidate is not None:
                discovered.append(candidate)
    except OSError:
        return []
    return discovered


def discovered_project_hash(child: Path, *, raw_base: str, slug_base: str, suffix_re):
    if not child.is_dir():
        return None
    chats = child / "chats"
    if not chats.is_dir():
        return None
    if not matches_project_name(child.name, raw_base=raw_base, slug_base=slug_base, suffix_re=suffix_re):
        return None
    return latest_session_mtime(chats), child.name


def matches_project_name(name: str, *, raw_base: str, slug_base: str, suffix_re) -> bool:
    return name == slug_base or name == raw_base or bool(suffix_re and suffix_re.match(name))


def latest_session_mtime(chats: Path) -> float:
    try:
        session_mtimes = [path.stat().st_mtime for path in chats.glob("session-*.json") if path.is_file()]
        return max(session_mtimes, default=chats.stat().st_mtime)
    except OSError:
        return 0.0


def ordered_candidates(discovered: list[tuple[float, str]], *, slug_base: str, raw_base: str, sha256_hash: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for _mtime, name in sorted(discovered, key=lambda item: item[0], reverse=True):
        add_candidate(candidates, seen, name)
    add_candidate(candidates, seen, slug_base)
    add_candidate(candidates, seen, raw_base)
    add_candidate(candidates, seen, sha256_hash)
    return candidates


def add_candidate(candidates: list[str], seen: set[str], value: str) -> None:
    token = (value or "").strip()
    if not token or token in seen:
        return
    seen.add(token)
    candidates.append(token)


__all__ = ['get_project_hash', 'project_hash_candidates']
