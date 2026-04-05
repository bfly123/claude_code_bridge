from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

_HASH_CACHE: dict[str, list[Path]] = {}
_HASH_CACHE_TS = 0.0


def normalize_project_path(value: str | Path) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        path = Path(raw).expanduser()
        try:
            path = path.resolve()
        except Exception:
            path = path.absolute()
        raw = str(path)
    except Exception:
        pass
    raw = raw.replace("\\", "/").rstrip("/")
    if os.name == "nt":
        raw = raw.lower()
    return raw


def project_root_marker(project_dir: Path) -> str:
    marker = Path(project_dir).expanduser() / ".project_root"
    if not marker.is_file():
        return ""
    try:
        return normalize_project_path(marker.read_text(encoding="utf-8").strip())
    except Exception:
        return ""


def slugify_project_hash(name: str) -> str:
    text = (name or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def compute_project_hashes(work_dir: Optional[Path] = None) -> tuple[str, str]:
    path = work_dir or Path.cwd()
    try:
        abs_path = path.expanduser().absolute()
    except Exception:
        abs_path = path
    basename_hash = slugify_project_hash(abs_path.name)
    sha256_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()
    return basename_hash, sha256_hash


def project_hash_candidates(work_dir: Optional[Path] = None, *, root: Optional[Path] = None) -> list[str]:
    path = work_dir or Path.cwd()
    try:
        abs_path = path.expanduser().absolute()
    except Exception:
        abs_path = path

    raw_base = (abs_path.name or "").strip()
    slug_base, sha256_hash = compute_project_hashes(abs_path)
    suffix_re = re.compile(rf"^{re.escape(slug_base)}-\d+$") if slug_base else None

    candidates: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        token = (value or "").strip()
        if not token or token in seen:
            return
        seen.add(token)
        candidates.append(token)

    root_path = Path(root).expanduser() if root else None
    discovered: list[tuple[float, str]] = []
    if root_path and root_path.is_dir() and slug_base:
        try:
            for child in root_path.iterdir():
                if not child.is_dir():
                    continue
                chats = child / "chats"
                if not chats.is_dir():
                    continue
                name = child.name
                if name == slug_base or name == raw_base or (suffix_re and suffix_re.match(name)):
                    try:
                        latest_mtime = max(
                            (p.stat().st_mtime for p in chats.glob("session-*.json") if p.is_file()),
                            default=chats.stat().st_mtime,
                        )
                    except OSError:
                        latest_mtime = 0.0
                    discovered.append((latest_mtime, name))
        except OSError:
            pass

    for _mtime, name in sorted(discovered, key=lambda item: item[0], reverse=True):
        _add(name)
    _add(slug_base)
    _add(raw_base)
    _add(sha256_hash)
    return candidates


def get_project_hash(work_dir: Optional[Path] = None, *, root: Path) -> str:
    path = work_dir or Path.cwd()
    root_path = Path(root).expanduser()
    candidates = project_hash_candidates(path, root=root_path)
    for project_hash in candidates:
        if (root_path / project_hash / "chats").is_dir():
            return project_hash
    return candidates[0] if candidates else ""


def work_dirs_for_hash(project_hash: str, *, root: Path) -> list[Path]:
    global _HASH_CACHE, _HASH_CACHE_TS
    now = time.time()
    root_path = Path(root).expanduser()
    if now - _HASH_CACHE_TS > 5.0:
        _HASH_CACHE = {}
        for wd in _iter_registry_work_dirs():
            try:
                hashes = project_hash_candidates(wd, root=root_path)
                for value in hashes:
                    _HASH_CACHE.setdefault(value, []).append(wd)
            except Exception:
                continue
        _HASH_CACHE_TS = now
    return _HASH_CACHE.get(project_hash, [])


def read_gemini_session_id(session_path: Path) -> str:
    if not session_path or not session_path.exists():
        return ""
    for _ in range(5):
        try:
            payload = json.loads(session_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            time.sleep(0.05)
            continue
        except Exception:
            return ""
        if isinstance(payload, dict) and isinstance(payload.get("sessionId"), str):
            return payload["sessionId"]
        return ""
    return ""


def _iter_registry_work_dirs() -> list[Path]:
    registry_dir = Path.home() / ".ccb" / "run"
    if not registry_dir.exists():
        return []
    work_dirs: list[Path] = []
    try:
        paths = list(registry_dir.glob("ccb-session-*.json"))
    except Exception:
        paths = []
    for path in paths:
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        wd = data.get("work_dir")
        if isinstance(wd, str) and wd.strip():
            try:
                work_dirs.append(Path(wd.strip()).expanduser())
            except Exception:
                continue
    return work_dirs
