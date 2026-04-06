from __future__ import annotations

from pathlib import Path

from runtime_env import env_bool
from provider_core.runtime_specs import ProviderClientSpec
from provider_sessions.files import find_project_session_file

from .explicit import _selected_session_file, resolve_work_dir


def resolve_work_dir_with_registry(
    spec: ProviderClientSpec,
    *,
    provider: str,
    cli_session_file: str | None = None,
    env_session_file: str | None = None,
    default_cwd: Path | None = None,
    registry_only_env: str = "CCB_REGISTRY_ONLY",
) -> tuple[Path, Path | None]:
    raw = _selected_session_file(cli_session_file, env_session_file)
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
    if found is not None:
        return cwd, found

    if env_bool(registry_only_env, False):
        raise ValueError(
            f"{registry_only_env}=1 is no longer supported for provider={provider!r}; "
            "use --session-file or run inside a .ccb project"
        )

    return cwd, None


__all__ = ["resolve_work_dir_with_registry"]
