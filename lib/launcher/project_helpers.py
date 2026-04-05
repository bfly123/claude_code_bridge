from __future__ import annotations

import os
from pathlib import Path


def project_config_dir(launcher, *, resolve_project_config_dir_fn) -> Path:
    return resolve_project_config_dir_fn(launcher.project_root)


def project_session_file(launcher, filename: str, *, resolve_project_config_dir_fn) -> Path:
    return project_config_dir(launcher, resolve_project_config_dir_fn=resolve_project_config_dir_fn) / filename


def normalize_cmd_config(raw: dict | None) -> dict:
    if raw is None or raw is False:
        return {"enabled": False}
    if isinstance(raw, bool):
        return {"enabled": bool(raw)}
    if isinstance(raw, str):
        return {"enabled": True, "start_cmd": raw.strip()}
    if isinstance(raw, dict):
        enabled = raw.get("enabled")
        if enabled is None:
            enabled = True
        start_cmd = raw.get("start_cmd") or raw.get("command") or raw.get("cmd") or ""
        title = raw.get("title") or raw.get("name") or "CCB-Cmd"
        return {
            "enabled": bool(enabled),
            "start_cmd": str(start_cmd).strip(),
            "title": str(title).strip() or "CCB-Cmd",
        }
    return {"enabled": False}


def cmd_settings(launcher) -> dict:
    cfg = launcher.cmd_config or {}
    if not cfg or not cfg.get("enabled"):
        return {"enabled": False}
    title = (cfg.get("title") or "CCB-Cmd").strip() or "CCB-Cmd"
    start_cmd = (cfg.get("start_cmd") or "").strip()
    if not start_cmd:
        start_cmd = launcher._default_cmd_start_cmd()
    return {"enabled": True, "title": title, "start_cmd": start_cmd}


def detect_terminal_type(*, detect_terminal_fn) -> str | None:
    forced = (os.environ.get("CCB_TERMINAL") or os.environ.get("CODEX_TERMINAL") or "").strip().lower()
    if forced == "tmux":
        return forced
    detected = detect_terminal_fn()
    if detected:
        return detected
    return None
