from __future__ import annotations

import shlex
from pathlib import Path
from typing import Callable

from provider_core.caller_env import caller_context_env


def build_start_cmd(
    command,
    spec,
    runtime_dir: Path,
    launch_session_id: str,
    *,
    load_resolved_provider_profile_fn: Callable[[Path], object | None],
    prepare_codex_home_overrides_fn: Callable[[Path, object | None], dict[str, str]],
    provider_start_parts_fn: Callable[[str], list[str]],
    load_resume_session_id_fn: Callable[[object, Path], str | None],
    build_codex_shell_prefix_fn: Callable[..., list[str]],
) -> str:
    profile = load_resolved_provider_profile_fn(runtime_dir)
    codex_home_overrides = prepare_codex_home_overrides_fn(runtime_dir, profile)
    codex_args = _codex_args(
        command,
        spec,
        runtime_dir,
        provider_start_parts_fn=provider_start_parts_fn,
        load_resume_session_id_fn=load_resume_session_id_fn,
    )
    env_map = _env_map(
        runtime_dir,
        launch_session_id,
        spec=spec,
        profile=profile,
        codex_home_overrides=codex_home_overrides,
    )
    prefix_parts = build_codex_shell_prefix_fn(profile=profile)
    exports = ' '.join(f'{key}={shlex.quote(str(value))}' for key, value in env_map.items() if str(value).strip())
    if exports:
        prefix_parts.append(f'export {exports}')
    cmd = ' '.join(shlex.quote(str(part)) for part in codex_args)
    if prefix_parts:
        return f"{'; '.join(prefix_parts)}; {cmd}"
    return cmd


def build_codex_shell_prefix(*, profile, provider_api_env_keys_fn: Callable[[str], list[str]]) -> list[str]:
    if profile is None or profile.inherit_api:
        return []
    return [f'unset {key}' for key in sorted(provider_api_env_keys_fn('codex'))]


def _codex_args(command, spec, runtime_dir: Path, *, provider_start_parts_fn, load_resume_session_id_fn) -> list[str]:
    codex_args = provider_start_parts_fn('codex')
    codex_args.extend(['-c', 'disable_paste_burst=true'])
    if command.auto_permission:
        codex_args.extend(
            [
                '-c',
                'trust_level="trusted"',
                '-c',
                'approval_policy="never"',
                '-c',
                'sandbox_mode="danger-full-access"',
            ]
        )
    codex_args.extend(spec.startup_args)
    if command.restore:
        session_id = load_resume_session_id_fn(spec, runtime_dir)
        if session_id:
            codex_args.extend(['resume', session_id])
    return codex_args


def _env_map(runtime_dir: Path, launch_session_id: str, *, spec, profile, codex_home_overrides: dict[str, str]) -> dict[str, str]:
    explicit_env: dict[str, str] = {}
    if profile is not None:
        explicit_env.update(profile.env)
    explicit_env.update(spec.env)
    return {
        **explicit_env,
        'CODEX_RUNTIME_DIR': str(runtime_dir),
        'CODEX_INPUT_FIFO': str(runtime_dir / 'input.fifo'),
        'CODEX_OUTPUT_FIFO': str(runtime_dir / 'output.fifo'),
        'CODEX_TERMINAL': 'tmux',
        **codex_home_overrides,
        **caller_context_env(actor=spec.name, runtime_dir=runtime_dir, launch_session_id=launch_session_id),
    }


__all__ = ['build_codex_shell_prefix', 'build_start_cmd']
