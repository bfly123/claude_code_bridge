from __future__ import annotations

import os
from pathlib import Path

from env_utils import env_bool
from provider_core.runtime_specs import ProviderClientSpec
from provider_sessions.files import CCB_PROJECT_CONFIG_DIRNAME, find_project_session_file


def resolve_work_dir(
    spec: ProviderClientSpec,
    *,
    cli_session_file: str | None = None,
    env_session_file: str | None = None,
    default_cwd: Path | None = None,
) -> tuple[Path, Path | None]:
    raw = (cli_session_file or "").strip() or (env_session_file or "").strip()
    if not raw:
        return (default_cwd or Path.cwd()), None

    expanded = os.path.expanduser(raw)
    session_path = Path(expanded)
    if os.environ.get("CLAUDECODE") == "1" and not session_path.is_absolute():
        raise ValueError(f"--session-file must be an absolute path in Claude Code (got: {raw})")

    try:
        session_path = session_path.resolve()
    except Exception:
        session_path = Path(expanded).absolute()

    if session_path.name != spec.session_filename:
        raise ValueError(
            f"Invalid session file for {spec.provider_key}: expected filename {spec.session_filename}, got {session_path.name}"
        )
    if not session_path.exists():
        raise ValueError(f"Session file not found: {session_path}")
    if not session_path.is_file():
        raise ValueError(f"Session file must be a file: {session_path}")

    if session_path.parent.name == CCB_PROJECT_CONFIG_DIRNAME:
        return session_path.parent.parent, session_path
    return session_path.parent, session_path


def resolve_work_dir_with_registry(
    spec: ProviderClientSpec,
    *,
    provider: str,
    cli_session_file: str | None = None,
    env_session_file: str | None = None,
    default_cwd: Path | None = None,
    registry_only_env: str = "CCB_REGISTRY_ONLY",
) -> tuple[Path, Path | None]:
    raw = (cli_session_file or "").strip() or (env_session_file or "").strip()
    if raw:
        return resolve_work_dir(
            spec,
            cli_session_file=cli_session_file,
            env_session_file=env_session_file,
            default_cwd=default_cwd,
        )

    cwd = default_cwd or Path.cwd()

    try:
        found = find_project_session_file(cwd, spec.session_filename)
    except Exception:
        found = None
    if found:
        return cwd, found

    if env_bool(registry_only_env, False):
        raise ValueError(
            f"{registry_only_env}=1 is no longer supported for provider={provider!r}; "
            "use --session-file or run inside a .ccb project"
        )

    return (cwd, None)


__all__ = ['resolve_work_dir', 'resolve_work_dir_with_registry']
