from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pane_registry import load_registry_by_claude_pane, load_registry_by_project_id, load_registry_by_session_id
from project_id import compute_ccb_project_id
from session_utils import find_project_session_file, project_config_dir


SESSION_ENV_KEYS = (
    "CCB_SESSION_ID",
    "CODEX_SESSION_ID",
    "GEMINI_SESSION_ID",
    "OPENCODE_SESSION_ID",
)


CLAUDE_PROJECTS_ROOT = Path(
    os.environ.get("CLAUDE_PROJECTS_ROOT")
    or os.environ.get("CLAUDE_PROJECT_ROOT")
    or (Path.home() / ".claude" / "projects")
).expanduser()


@dataclass
class ClaudeSessionResolution:
    data: dict
    session_file: Optional[Path]
    registry: Optional[dict]
    source: str


def _read_json(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _pane_from_data(data: dict) -> str:
    pane_id = str(data.get("pane_id") or "").strip()
    if pane_id:
        return pane_id
    legacy = str(data.get("claude_pane_id") or "").strip()
    if legacy:
        return legacy
    if (data.get("terminal") or "").strip().lower() == "tmux":
        return str(data.get("tmux_session") or "").strip()
    return ""


def _session_file_from_record(record: dict) -> Optional[Path]:
    providers = record.get("providers") if isinstance(record.get("providers"), dict) else {}
    claude = providers.get("claude") if isinstance(providers, dict) else None
    path_str = None
    if isinstance(claude, dict):
        path_str = claude.get("session_file")
    if not path_str:
        path_str = record.get("claude_session_file") or record.get("session_file")
    if not path_str:
        return None
    try:
        return Path(str(path_str)).expanduser()
    except Exception:
        return None


def _data_from_registry(record: dict, fallback_work_dir: Path) -> dict:
    data: dict = {}
    if not isinstance(record, dict):
        return data

    data["ccb_project_id"] = record.get("ccb_project_id")
    data["work_dir"] = record.get("work_dir") or str(fallback_work_dir)
    data["terminal"] = record.get("terminal")

    providers = record.get("providers") if isinstance(record.get("providers"), dict) else {}
    claude = providers.get("claude") if isinstance(providers, dict) else None
    if isinstance(claude, dict):
        pane_id = claude.get("pane_id")
        if pane_id:
            data["pane_id"] = pane_id
        marker = claude.get("pane_title_marker")
        if marker:
            data["pane_title_marker"] = marker
        if claude.get("claude_session_id"):
            data["claude_session_id"] = claude.get("claude_session_id")
        if claude.get("claude_session_path"):
            data["claude_session_path"] = claude.get("claude_session_path")

    if record.get("claude_pane_id"):
        data.setdefault("pane_id", record.get("claude_pane_id"))
    if record.get("claude_session_id"):
        data.setdefault("claude_session_id", record.get("claude_session_id"))
    if record.get("claude_session_path"):
        data.setdefault("claude_session_path", record.get("claude_session_path"))

    return data


def _select_resolution(data: dict, session_file: Optional[Path], record: Optional[dict], source: str) -> ClaudeSessionResolution:
    return ClaudeSessionResolution(
        data=data,
        session_file=session_file,
        registry=record,
        source=source,
    )


def _candidate_default_session_file(work_dir: Path) -> Optional[Path]:
    try:
        cfg = project_config_dir(work_dir)
    except Exception:
        return None
    return cfg / ".claude-session"


def _registry_run_dir() -> Path:
    return Path.home() / ".ccb" / "run"


def _registry_updated_at(data: dict, path: Path) -> int:
    value = data.get("updated_at")
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        try:
            return int(value.strip())
        except Exception:
            pass
    try:
        return int(path.stat().st_mtime)
    except Exception:
        return 0


def _project_key_for_path(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _candidate_project_dirs(root: Path, work_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    env_pwd = os.environ.get("PWD")
    if env_pwd:
        try:
            candidates.append(Path(env_pwd))
        except Exception:
            pass
    candidates.append(work_dir)
    try:
        candidates.append(work_dir.resolve())
    except Exception:
        pass

    out: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _project_key_for_path(candidate)
        if key in seen:
            continue
        seen.add(key)
        out.append(root / key)
    return out


def _session_path_from_id(session_id: str, work_dir: Path) -> Optional[Path]:
    sid = str(session_id or "").strip()
    if not sid:
        return None
    for project_dir in _candidate_project_dirs(CLAUDE_PROJECTS_ROOT, work_dir):
        candidate = project_dir / f"{sid}.jsonl"
        if candidate.exists():
            return candidate
    return None


def _normalize_session_binding(data: dict, work_dir: Path) -> None:
    if not isinstance(data, dict):
        return
    sid = str(data.get("claude_session_id") or data.get("session_id") or "").strip()
    path_value = str(data.get("claude_session_path") or "").strip()
    path: Optional[Path] = None
    if path_value:
        try:
            path = Path(path_value).expanduser()
        except Exception:
            path = None
    if path and path.exists():
        if sid and path.stem != sid:
            candidate = _session_path_from_id(sid, work_dir)
            if candidate and candidate.exists():
                data["claude_session_path"] = str(candidate)
            else:
                data["claude_session_id"] = path.stem
        elif not sid:
            data["claude_session_id"] = path.stem
        return
    if sid:
        candidate = _session_path_from_id(sid, work_dir)
        if candidate and candidate.exists():
            data["claude_session_path"] = str(candidate)


def _load_registry_by_project_id_unfiltered(ccb_project_id: str, work_dir: Path) -> Optional[dict]:
    if not ccb_project_id:
        return None
    run_dir = _registry_run_dir()
    if not run_dir.exists():
        return None
    best: Optional[dict] = None
    best_ts = -1
    for path in sorted(run_dir.glob("ccb-session-*.json")):
        try:
            data = _read_json(path)
        except Exception:
            continue
        if not data:
            continue
        pid = str(data.get("ccb_project_id") or "").strip()
        if not pid:
            wd = str(data.get("work_dir") or "").strip()
            if wd:
                try:
                    pid = compute_ccb_project_id(Path(wd))
                except Exception:
                    pid = ""
        if pid != ccb_project_id:
            continue
        ts = _registry_updated_at(data, path)
        if ts > best_ts:
            best_ts = ts
            best = data
    return best


def resolve_claude_session(work_dir: Path) -> Optional[ClaudeSessionResolution]:
    best_fallback: Optional[ClaudeSessionResolution] = None
    try:
        current_pid = compute_ccb_project_id(work_dir)
    except Exception:
        current_pid = ""
    strict_project = (Path(work_dir) / ".ccb_config").is_dir()
    allow_cross = os.environ.get("CCB_ALLOW_CROSS_PROJECT_SESSION") in ("1", "true", "yes")
    if not strict_project and not allow_cross:
        return None

    def _record_project_id(record: dict) -> str:
        if not isinstance(record, dict):
            return ""
        pid = str(record.get("ccb_project_id") or "").strip()
        if pid:
            return pid
        wd = str(record.get("work_dir") or "").strip()
        if not wd:
            return ""
        try:
            return compute_ccb_project_id(Path(wd))
        except Exception:
            return ""

    def consider(candidate: Optional[ClaudeSessionResolution]) -> Optional[ClaudeSessionResolution]:
        nonlocal best_fallback
        if not candidate:
            return None
        _normalize_session_binding(candidate.data, work_dir)
        if _pane_from_data(candidate.data):
            return candidate
        if best_fallback is None:
            best_fallback = candidate
        return None

    # 1) Registry via session id envs
    for key in SESSION_ENV_KEYS:
        session_id = (os.environ.get(key) or "").strip()
        if not session_id:
            continue
        record = load_registry_by_session_id(session_id)
        if not isinstance(record, dict):
            continue
        if not allow_cross and strict_project:
            record_pid = _record_project_id(record)
            if not record_pid or (current_pid and record_pid != current_pid):
                continue
        data = _data_from_registry(record, work_dir)
        session_file = _session_file_from_record(record) or find_project_session_file(work_dir, ".claude-session")
        candidate = _select_resolution(data, session_file, record, f"registry:{key}")
        resolved = consider(candidate)
        if resolved:
            return resolved
        break

    # 2) Registry via ccb_project_id
    try:
        pid = compute_ccb_project_id(work_dir)
    except Exception:
        pid = ""
    if pid:
        record = load_registry_by_project_id(pid, "claude")
        if isinstance(record, dict):
            data = _data_from_registry(record, work_dir)
            session_file = _session_file_from_record(record) or find_project_session_file(work_dir, ".claude-session")
            candidate = _select_resolution(data, session_file, record, "registry:project")
            resolved = consider(candidate)
            if resolved:
                return resolved

        # Fallback: accept latest registry record even if pane liveness can't be verified.
        unfiltered = _load_registry_by_project_id_unfiltered(pid, work_dir)
        if isinstance(unfiltered, dict):
            data = _data_from_registry(unfiltered, work_dir)
            session_file = _session_file_from_record(unfiltered) or find_project_session_file(work_dir, ".claude-session")
            candidate = _select_resolution(data, session_file, unfiltered, "registry:project_unfiltered")
            resolved = consider(candidate)
            if resolved:
                return resolved

    # 3) .claude-session file
    session_file = find_project_session_file(work_dir, ".claude-session")
    if session_file:
        data = _read_json(session_file)
        if data:
            data.setdefault("work_dir", str(work_dir))
            _normalize_session_binding(data, work_dir)
            candidate = _select_resolution(data, session_file, None, "session_file")
            resolved = consider(candidate)
            if resolved:
                return resolved

    # 4) Registry via current pane id
    pane_id = (os.environ.get("WEZTERM_PANE") or os.environ.get("TMUX_PANE") or "").strip()
    if pane_id:
        record = load_registry_by_claude_pane(pane_id)
        if isinstance(record, dict):
            if not allow_cross and strict_project:
                record_pid = _record_project_id(record)
                if not record_pid or (current_pid and record_pid != current_pid):
                    record = None
            if record:
                data = _data_from_registry(record, work_dir)
                session_file = _session_file_from_record(record) or find_project_session_file(work_dir, ".claude-session")
                candidate = _select_resolution(data, session_file, record, "registry:pane")
                resolved = consider(candidate)
                if resolved:
                    return resolved

    if best_fallback:
        if not best_fallback.session_file:
            best_fallback.session_file = _candidate_default_session_file(work_dir)
        return best_fallback

    return None
