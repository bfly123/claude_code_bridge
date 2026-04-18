from __future__ import annotations

from pathlib import Path
import os
import shutil

from cli.management_runtime.versioning_runtime.local import get_version_info


_LEGACY_BIN_DIR = Path.home() / '.local' / 'bin'


def build_tmux_backend(socket_path: str):
    try:
        from terminal_runtime import TmuxBackend

        return TmuxBackend(socket_path=socket_path)
    except Exception:
        return None


def current_install_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _candidate_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    runtime_root = current_install_root()
    roots.append(runtime_root)

    ccb_path = resolve_ccb_executable()
    if ccb_path is not None:
        roots.append(ccb_path.parent)

    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return tuple(deduped)


def resolve_ccb_executable() -> Path | None:
    runtime_ccb = current_install_root() / 'ccb'
    if runtime_ccb.is_file():
        return runtime_ccb

    installed = shutil.which('ccb')
    if installed:
        path = Path(installed).expanduser()
        if path.is_file():
            return path.resolve()

    legacy = _LEGACY_BIN_DIR / 'ccb'
    if legacy.is_file():
        return legacy
    return None


def script_path(script_name: str) -> str | None:
    for root in _candidate_roots():
        runtime_copy = root / 'config' / script_name
        if runtime_copy.is_file():
            return str(runtime_copy)

    installed = shutil.which(script_name)
    if installed:
        path = Path(installed).expanduser()
        if path.is_file():
            return str(path.resolve())

    legacy = _LEGACY_BIN_DIR / script_name
    if legacy.is_file():
        return str(legacy)

    repo_copy = current_install_root() / 'config' / script_name
    if repo_copy.is_file():
        return str(repo_copy)
    return None


def detect_ccb_version() -> str:
    env_version = str(os.environ.get('CCB_VERSION') or '').strip()
    if env_version:
        return env_version

    for root in _candidate_roots():
        try:
            version = str(get_version_info(root).get('version') or '').strip()
        except Exception:
            version = ''
        if version:
            return version
    return '?'


__all__ = [
    'build_tmux_backend',
    'current_install_root',
    'detect_ccb_version',
    'resolve_ccb_executable',
    'script_path',
]
