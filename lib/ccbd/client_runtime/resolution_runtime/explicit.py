from __future__ import annotations

import os
from pathlib import Path

from provider_core.runtime_specs import ProviderClientSpec
from provider_sessions.files import CCB_PROJECT_CONFIG_DIRNAME


def _selected_session_file(cli_session_file: str | None, env_session_file: str | None) -> str:
    return (cli_session_file or "").strip() or (env_session_file or "").strip()


def _resolved_session_path(raw: str) -> Path:
    expanded = os.path.expanduser(raw)
    session_path = Path(expanded)
    if os.environ.get("CLAUDECODE") == "1" and not session_path.is_absolute():
        raise ValueError(f"--session-file must be an absolute path in Claude Code (got: {raw})")
    try:
        return session_path.resolve()
    except Exception:
        return Path(expanded).absolute()


def _validate_session_path(spec: ProviderClientSpec, session_path: Path) -> None:
    if session_path.name != spec.session_filename:
        raise ValueError(
            f"Invalid session file for {spec.provider_key}: expected filename {spec.session_filename}, got {session_path.name}"
        )
    if not session_path.exists():
        raise ValueError(f"Session file not found: {session_path}")
    if not session_path.is_file():
        raise ValueError(f"Session file must be a file: {session_path}")


def _work_dir_from_session_path(session_path: Path) -> Path:
    if session_path.parent.name == CCB_PROJECT_CONFIG_DIRNAME:
        return session_path.parent.parent
    return session_path.parent


def resolve_work_dir(
    spec: ProviderClientSpec,
    *,
    cli_session_file: str | None = None,
    env_session_file: str | None = None,
    default_cwd: Path | None = None,
) -> tuple[Path, Path | None]:
    raw = _selected_session_file(cli_session_file, env_session_file)
    if not raw:
        return (default_cwd or Path.cwd()), None

    session_path = _resolved_session_path(raw)
    _validate_session_path(spec, session_path)
    return _work_dir_from_session_path(session_path), session_path


__all__ = ["resolve_work_dir"]
