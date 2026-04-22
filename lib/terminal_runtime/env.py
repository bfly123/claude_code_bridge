from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
import re


_TRUE_VALUES = {'1', 'true', 'yes', 'on'}


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.0, value)


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def sanitize_filename(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")


def is_windows() -> bool:
    return os.name == "nt" or sys.platform == "win32"


def experimental_windows_native_enabled() -> bool:
    raw = str(os.environ.get('CCB_EXPERIMENTAL_WINDOWS_NATIVE') or '').strip().lower()
    return raw in _TRUE_VALUES


def subprocess_kwargs() -> dict:
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return {"creationflags": flags}
    return {}


def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except Exception:
        return False

def default_shell(*, is_wsl_fn, is_windows_fn) -> tuple[str, str]:
    if is_wsl_fn():
        return "bash", "-c"
    if is_windows_fn():
        for shell in ["pwsh", "powershell"]:
            if shutil.which(shell):
                return shell, "-Command"
        return "powershell", "-Command"
    return "bash", "-c"
