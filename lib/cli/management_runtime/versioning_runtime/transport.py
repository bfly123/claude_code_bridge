from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request


def fetch_json_via_urllib(url: str, *, timeout: float, user_agent: str = "ccb"):
    import ssl

    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_json_via_curl(url: str, *, timeout: float):
    if not shutil.which("curl"):
        return None
    result = subprocess.run(
        ["curl", "-fsSL", url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except Exception:
        return None


__all__ = ['fetch_json_via_curl', 'fetch_json_via_urllib']
