---
name: mounted
description: Report which CCB providers are mounted (session exists AND daemon is online). Outputs JSON.
metadata:
  short-description: Show mounted CCB providers as JSON
---

# Mounted Providers (JSON)

Reports which CCB providers are considered "mounted" for the current project.

## Definition (Mode B)

For each provider, `mounted = has_session && daemon_on`.

## Execution

```bash
python3 - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path


PROVIDERS = ["codex", "gemini", "opencode", "claude", "droid"]
DAEMONS = {
    "codex": "cask",
    "gemini": "gask",
    "opencode": "oask",
    "claude": "lask",
    "droid": "dask",
}


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def daemon_status(daemon: str) -> dict:
    pidfile = Path(os.environ.get("TMPDIR") or "/tmp") / f"ccb-{daemon}d.pid"
    if not pidfile.exists():
        return {"daemon": daemon, "pid": None, "pidfile": str(pidfile), "online": False}
    try:
        raw = pidfile.read_text(encoding="utf-8", errors="ignore").strip()
        pid = int(raw)
    except Exception:
        return {"daemon": daemon, "pid": None, "pidfile": str(pidfile), "online": False, "error": "invalid_pidfile"}
    return {"daemon": daemon, "pid": pid, "pidfile": str(pidfile), "online": _pid_alive(pid)}


def session_paths(provider: str, cwd: Path) -> list[str]:
    name = f".{provider}-session"
    return [
        str(cwd / ".ccb_config" / name),
        str(cwd / name),
    ]


cwd = Path.cwd()
out: dict = {
    "cwd": str(cwd),
    "mode": "B",
    "definition": "mounted = has_session && daemon_on",
    "providers": [],
    "mounted_providers": [],
}

for p in PROVIDERS:
    paths = session_paths(p, cwd)
    existing = [sp for sp in paths if Path(sp).is_file()]
    has_session = bool(existing)
    d = DAEMONS[p]
    dstat = daemon_status(d)
    daemon_on = bool(dstat.get("online"))
    mounted = has_session and daemon_on
    reason: str | None = None
    if not mounted:
        if not has_session and not daemon_on:
            reason = "no_session_and_daemon_off"
        elif not has_session:
            reason = "no_session"
        else:
            reason = "daemon_off"

    rec = {
        "provider": p,
        "daemon": d,
        "daemon_status": dstat,
        "session_candidates": paths,
        "session_existing": existing,
        "has_session": has_session,
        "daemon_on": daemon_on,
        "mounted": mounted,
        "reason": reason,
    }
    out["providers"].append(rec)
    if mounted:
        out["mounted_providers"].append(p)

print(json.dumps(out, ensure_ascii=False, indent=2))
PY
```
