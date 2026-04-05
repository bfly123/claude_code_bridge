"""Backend environment detection for Windows/WSL runtime integration."""
from __future__ import annotations

import os
import subprocess
import sys

from terminal_runtime.env import subprocess_kwargs as _subprocess_kwargs


def get_backend_env() -> str | None:
    """Get backend environment from explicit env or platform default."""
    v = (os.environ.get("CCB_BACKEND_ENV") or "").strip().lower()
    if v in {"wsl", "windows"}:
        return v
    return "windows" if sys.platform == "win32" else None


def _wsl_probe_distro_and_home() -> tuple[str, str]:
    """Probe default WSL distro and home directory"""
    try:
        r = subprocess.run(
            ["wsl.exe", "-e", "sh", "-lc", "echo $WSL_DISTRO_NAME; echo $HOME"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            **_subprocess_kwargs(),
        )
        if r.returncode == 0:
            lines = r.stdout.strip().split("\n")
            if len(lines) >= 2:
                return lines[0].strip(), lines[1].strip()
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["wsl.exe", "-l", "-q"],
            capture_output=True,
            text=True,
            encoding="utf-16-le",
            errors="replace",
            timeout=5,
            **_subprocess_kwargs(),
        )
        if r.returncode == 0:
            for line in r.stdout.strip().split("\n"):
                distro = line.strip().strip("\x00")
                if distro:
                    break
            else:
                distro = "Ubuntu"
        else:
            distro = "Ubuntu"
    except Exception:
        distro = "Ubuntu"
    try:
        r = subprocess.run(
            ["wsl.exe", "-d", distro, "-e", "sh", "-lc", "echo $HOME"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            **_subprocess_kwargs(),
        )
        home = r.stdout.strip() if r.returncode == 0 else "/root"
    except Exception:
        home = "/root"
    return distro, home


def apply_backend_env() -> None:
    """Apply BackendEnv=wsl settings (set session root paths for Windows to access WSL)"""
    if sys.platform != "win32" or get_backend_env() != "wsl":
        return
    if os.environ.get("CODEX_SESSION_ROOT") and os.environ.get("GEMINI_ROOT"):
        return
    distro, home = _wsl_probe_distro_and_home()
    for base in (fr"\\wsl.localhost\{distro}", fr"\\wsl$\{distro}"):
        prefix = base + home.replace("/", "\\")
        codex_path = prefix + r"\.codex\sessions"
        gemini_path = prefix + r"\.gemini\tmp"
        if Path(codex_path).exists() or Path(gemini_path).exists():
            os.environ.setdefault("CODEX_SESSION_ROOT", codex_path)
            os.environ.setdefault("GEMINI_ROOT", gemini_path)
            return
    prefix = fr"\\wsl.localhost\{distro}" + home.replace("/", "\\")
    os.environ.setdefault("CODEX_SESSION_ROOT", prefix + r"\.codex\sessions")
    os.environ.setdefault("GEMINI_ROOT", prefix + r"\.gemini\tmp")


__all__ = ["apply_backend_env", "get_backend_env"]
