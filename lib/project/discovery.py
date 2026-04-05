from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CCB_DIRNAME = '.ccb'
WORKSPACE_BINDING_FILENAME = '.ccb-workspace.json'


class ProjectDiscoveryError(ValueError):
    pass


def project_ccb_dir(project_root: Path) -> Path:
    return Path(project_root).expanduser().resolve() / CCB_DIRNAME


def global_ccb_dir() -> Path:
    return Path.home() / CCB_DIRNAME


def find_current_project_anchor(start_dir: Path) -> Path | None:
    current = Path(start_dir).expanduser()
    try:
        current = current.resolve()
    except Exception:
        current = current.absolute()
    if _project_anchor_dir(current) is None:
        return None
    return current


def find_nearest_project_anchor(start_dir: Path) -> Path | None:
    current = Path(start_dir).expanduser()
    try:
        current = current.resolve()
    except Exception:
        current = current.absolute()
    for root in (current, *current.parents):
        if _project_anchor_dir(root) is None:
            continue
        is_dangerous, _reason = is_dangerous_project_root(root)
        if root != current and is_dangerous:
            continue
        return root
    return None


def find_parent_project_anchor_dir(start_dir: Path) -> Path | None:
    current = Path(start_dir).expanduser()
    try:
        current = current.resolve()
    except Exception:
        current = current.absolute()
    for root in current.parents:
        candidate = _project_anchor_dir(root)
        if candidate is None:
            continue
        is_dangerous, _reason = is_dangerous_project_root(root)
        if is_dangerous:
            continue
        return candidate
    return None


def is_dangerous_project_root(start_dir: Path) -> tuple[bool, str]:
    current = Path(start_dir).expanduser()
    try:
        current = current.resolve()
    except Exception:
        current = current.absolute()

    try:
        home = Path.home().resolve()
    except Exception:
        try:
            home = Path.home().absolute()
        except Exception:
            home = None

    if home is not None and current == home:
        return True, '$HOME'

    try:
        anchor = Path(current.anchor) if current.anchor else None
    except Exception:
        anchor = None
    if anchor is not None and current == anchor:
        return True, 'filesystem root'
    return False, ''


def _project_anchor_dir(root: Path) -> Path | None:
    primary = root / CCB_DIRNAME
    return primary if primary.is_dir() else None


def find_workspace_binding(start_dir: Path) -> Path | None:
    current = Path(start_dir).expanduser()
    try:
        current = current.resolve()
    except Exception:
        current = current.absolute()
    for root in (current, *current.parents):
        candidate = root / WORKSPACE_BINDING_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_workspace_binding(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception as exc:
        raise ProjectDiscoveryError(f'cannot read workspace binding {path}: {exc}') from exc
    if not isinstance(data, dict):
        raise ProjectDiscoveryError(f'workspace binding {path} must contain an object')
    target_project = data.get('target_project')
    if not isinstance(target_project, str) or not target_project.strip():
        raise ProjectDiscoveryError(f'workspace binding {path} is missing target_project')
    return data
