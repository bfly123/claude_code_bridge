from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import time
from typing import Callable


def terminate_provider_session(
    provider: str,
    *,
    cwd: Path,
    session_finder: Callable[[Path, str], Path | None],
    tmux_backend_factory: Callable[[], object],
    safe_write_session: Callable[[Path, str], tuple[bool, str | None]],
) -> None:
    session_file = session_finder(cwd, f".{provider}-session")
    if not _session_file_exists(session_file):
        _print_missing_session(provider)
        return

    try:
        data = json.loads(session_file.read_text(encoding="utf-8-sig"))
        _terminate_tmux_target(data, tmux_backend_factory=tmux_backend_factory)
        _mark_session_ended(data)
        safe_write_session(session_file, json.dumps(data, ensure_ascii=False, indent=2))
        _print_terminated(provider)
    except Exception as exc:
        _print_termination_error(provider, exc)


def _session_file_exists(session_file: Path | None) -> bool:
    return bool(session_file and session_file.exists())


def _print_missing_session(provider: str) -> None:
    print(f"ℹ️  {provider}: No active session file found")


def _terminate_tmux_target(data: dict, *, tmux_backend_factory: Callable[[], object]) -> None:
    pane_id_text = _pane_target(data)
    if not pane_id_text or not shutil.which("tmux"):
        return
    backend = tmux_backend_factory()
    if pane_id_text.startswith("%"):
        backend.kill_pane(pane_id_text)
        return
    tmux_session = _tmux_session_name(data)
    if tmux_session:
        _kill_tmux_session_pair(tmux_session)
        return
    backend.kill_pane(pane_id_text)


def _pane_target(data: dict) -> str:
    return str(data.get("pane_id") or data.get("tmux_session") or "").strip()


def _tmux_session_name(data: dict) -> str:
    tmux_session = str(data.get("tmux_session") or "").strip()
    if tmux_session and not tmux_session.startswith("%"):
        return tmux_session
    return ""


def _kill_tmux_session_pair(tmux_session: str) -> None:
    subprocess.run(["tmux", "kill-session", "-t", tmux_session], stderr=subprocess.DEVNULL)
    subprocess.run(["tmux", "kill-session", "-t", f"launcher-{tmux_session}"], stderr=subprocess.DEVNULL)


def _mark_session_ended(data: dict) -> None:
    data["active"] = False
    data["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")


def _print_terminated(provider: str) -> None:
    print(f"✅ {provider.capitalize()} session terminated")


def _print_termination_error(provider: str, exc: Exception) -> None:
    print(f"❌ {provider}: {exc}")


__all__ = ["terminate_provider_session"]
