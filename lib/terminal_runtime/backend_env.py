from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

from .env import experimental_windows_native_enabled, is_windows, is_wsl
from .env import subprocess_kwargs as _subprocess_kwargs


def get_backend_env() -> str | None:
    raw = str(os.environ.get('CCB_BACKEND_ENV') or '').strip().lower()
    if raw in {'wsl', 'windows'}:
        return raw
    return 'windows' if sys.platform == 'win32' else None


def _run_wsl(
    args: list[str],
    *,
    encoding: str = 'utf-8',
    timeout: int = 5,
):
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding=encoding,
        errors='replace',
        timeout=timeout,
        **_subprocess_kwargs(),
    )


def _probe_wsl_env() -> tuple[str, str] | None:
    try:
        result = _run_wsl(
            ['wsl.exe', '-e', 'sh', '-lc', 'echo $WSL_DISTRO_NAME; echo $HOME'],
            timeout=10,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    lines = result.stdout.strip().split('\n')
    if len(lines) < 2:
        return None
    return lines[0].strip(), lines[1].strip()


def _probe_default_distro() -> str:
    try:
        result = _run_wsl(['wsl.exe', '-l', '-q'], encoding='utf-16-le')
    except Exception:
        return 'Ubuntu'
    if result.returncode != 0:
        return 'Ubuntu'
    for line in result.stdout.strip().split('\n'):
        distro = line.strip().strip('\x00')
        if distro:
            return distro
    return 'Ubuntu'


def _probe_distro_home(distro: str) -> str:
    try:
        result = _run_wsl(['wsl.exe', '-d', distro, '-e', 'sh', '-lc', 'echo $HOME'])
    except Exception:
        return '/root'
    return result.stdout.strip() if result.returncode == 0 else '/root'


def _wsl_probe_distro_and_home() -> tuple[str, str]:
    probed = _probe_wsl_env()
    if probed is not None:
        return probed
    distro = _probe_default_distro()
    return distro, _probe_distro_home(distro)


def _wsl_prefixes(distro: str, home: str) -> tuple[str, ...]:
    suffix = home.replace('/', '\\')
    return (
        fr'\\wsl.localhost\{distro}' + suffix,
        fr'\\wsl$\{distro}' + suffix,
    )


def _session_roots(prefix: str) -> tuple[str, str]:
    return (
        prefix + r'\.codex\sessions',
        prefix + r'\.gemini\tmp',
    )


def _apply_existing_wsl_session_roots(distro: str, home: str) -> bool:
    for prefix in _wsl_prefixes(distro, home):
        codex_path, gemini_path = _session_roots(prefix)
        if Path(codex_path).exists() or Path(gemini_path).exists():
            os.environ.setdefault('CODEX_SESSION_ROOT', codex_path)
            os.environ.setdefault('GEMINI_ROOT', gemini_path)
            return True
    return False


def _apply_fallback_wsl_session_roots(distro: str, home: str) -> None:
    prefix = _wsl_prefixes(distro, home)[0]
    codex_path, gemini_path = _session_roots(prefix)
    os.environ.setdefault('CODEX_SESSION_ROOT', codex_path)
    os.environ.setdefault('GEMINI_ROOT', gemini_path)


def apply_backend_env() -> None:
    if sys.platform != 'win32' or get_backend_env() != 'wsl':
        return
    if os.environ.get('CODEX_SESSION_ROOT') and os.environ.get('GEMINI_ROOT'):
        return
    distro, home = _wsl_probe_distro_and_home()
    if _apply_existing_wsl_session_roots(distro, home):
        return
    _apply_fallback_wsl_session_roots(distro, home)


def default_mux_backend_impl() -> str:
    raw = str(os.environ.get('CCB_BACKEND_IMPL') or '').strip().lower()
    if raw in {'tmux', 'psmux'}:
        return raw
    if is_windows() and not is_wsl() and experimental_windows_native_enabled():
        return 'psmux'
    return 'tmux'


def mux_backend_available(backend_impl: str) -> bool:
    executable = 'psmux' if str(backend_impl).strip().lower() == 'psmux' else 'tmux'
    return shutil.which(executable) is not None


__all__ = [
    'apply_backend_env',
    'default_mux_backend_impl',
    'get_backend_env',
    'mux_backend_available',
]
