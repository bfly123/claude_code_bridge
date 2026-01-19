from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional, Tuple


CONFIG_FILENAME = "ccb.config"
DEFAULT_PROVIDERS = ["codex", "gemini", "opencode", "claude"]


@dataclass
class StartConfig:
    data: dict
    path: Optional[Path] = None


_ALLOWED_PROVIDERS = {"codex", "gemini", "opencode", "claude"}


def _parse_tokens(raw: str) -> list[str]:
    if not raw:
        return []
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = line
        if "//" in stripped:
            stripped = stripped.split("//", 1)[0]
        if "#" in stripped:
            stripped = stripped.split("#", 1)[0]
        lines.append(stripped)
    cleaned = " ".join(lines)
    cleaned = re.sub(r"[\[\]\{\}\"']", " ", cleaned)
    parts = re.split(r"[,\s]+", cleaned)
    return [p for p in (part.strip() for part in parts) if p]


def _normalize_providers(tokens: list[str]) -> tuple[list[str], bool]:
    providers: list[str] = []
    seen: set[str] = set()
    cmd_enabled = False
    for raw in tokens:
        token = str(raw).strip().lower()
        if not token:
            continue
        if token == "cmd":
            cmd_enabled = True
            continue
        if token not in _ALLOWED_PROVIDERS:
            continue
        if token in seen:
            continue
        seen.add(token)
        providers.append(token)
    return providers, cmd_enabled


def _parse_config_obj(obj: object) -> dict:
    if isinstance(obj, dict):
        data = dict(obj)
        raw_providers = data.get("providers")
        tokens: list[str] = []
        if isinstance(raw_providers, str):
            tokens = _parse_tokens(raw_providers)
        elif isinstance(raw_providers, list):
            tokens = [str(p) for p in raw_providers if p is not None]
        elif raw_providers is not None:
            tokens = [str(raw_providers)]

        if tokens:
            providers, cmd_enabled = _normalize_providers(tokens)
            data["providers"] = providers
            if cmd_enabled and "cmd" not in data:
                data["cmd"] = True
        return data

    if isinstance(obj, list):
        tokens = [str(p) for p in obj if p is not None]
        providers, cmd_enabled = _normalize_providers(tokens)
        data: dict = {"providers": providers}
        if cmd_enabled:
            data["cmd"] = True
        return data

    if isinstance(obj, str):
        tokens = _parse_tokens(obj)
        providers, cmd_enabled = _normalize_providers(tokens)
        data = {"providers": providers}
        if cmd_enabled:
            data["cmd"] = True
        return data

    return {}


def _read_config(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        obj = json.loads(raw)
    except Exception:
        obj = None
    if obj is None:
        tokens = _parse_tokens(raw)
        providers, cmd_enabled = _normalize_providers(tokens)
        data: dict = {"providers": providers}
        if cmd_enabled:
            data["cmd"] = True
        return data
    return _parse_config_obj(obj)


def _config_paths(work_dir: Path) -> Tuple[Path, Path]:
    project = Path(work_dir) / ".ccb_config" / CONFIG_FILENAME
    global_path = Path.home() / ".ccb" / CONFIG_FILENAME
    return project, global_path


def load_start_config(work_dir: Path) -> StartConfig:
    project, global_path = _config_paths(work_dir)
    if project.exists():
        return StartConfig(data=_read_config(project), path=project)
    if global_path.exists():
        return StartConfig(data=_read_config(global_path), path=global_path)
    return StartConfig(data={}, path=None)


def ensure_default_start_config(work_dir: Path) -> Tuple[Optional[Path], bool]:
    project, _global_path = _config_paths(work_dir)
    if project.exists():
        return project, False
    try:
        project.parent.mkdir(parents=True, exist_ok=True)
        payload = ",".join(DEFAULT_PROVIDERS) + "\n"
        project.write_text(payload, encoding="utf-8")
        return project, True
    except Exception:
        return None, False
