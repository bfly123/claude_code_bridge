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
    if not session_file or not session_file.exists():
        print(f"ℹ️  {provider}: No active session file found")
        return

    try:
        data = json.loads(session_file.read_text(encoding="utf-8-sig"))
        pane_id = data.get("pane_id") or data.get("tmux_session") or ""

        if pane_id and shutil.which("tmux"):
            backend = tmux_backend_factory()
            pane_id_text = str(pane_id)
            if pane_id_text.startswith("%"):
                backend.kill_pane(pane_id_text)
            else:
                tmux_session = str(data.get("tmux_session") or "").strip()
                if tmux_session and not tmux_session.startswith("%"):
                    subprocess.run(["tmux", "kill-session", "-t", tmux_session], stderr=subprocess.DEVNULL)
                    subprocess.run(["tmux", "kill-session", "-t", f"launcher-{tmux_session}"], stderr=subprocess.DEVNULL)
                else:
                    backend.kill_pane(pane_id_text)

        data["active"] = False
        data["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        safe_write_session(session_file, json.dumps(data, ensure_ascii=False, indent=2))
        print(f"✅ {provider.capitalize()} session terminated")
    except Exception as exc:
        print(f"❌ {provider}: {exc}")


__all__ = ["terminate_provider_session"]
