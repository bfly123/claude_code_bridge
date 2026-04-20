from __future__ import annotations

import shlex

from provider_profiles import provider_api_env_keys


def build_claude_env_prefix(
    *,
    profile=None,
    extra_env: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
    should_drop_base_url_fn,
    claude_user_base_url_fn,
) -> str:
    api_keys = provider_api_env_keys("claude")
    explicit_env = collect_explicit_api_env(profile=profile, extra_env=extra_env, api_keys=api_keys)
    parts = unset_api_env_parts(profile=profile, api_keys=api_keys)

    explicit_env = reconcile_base_url(
        explicit_env,
        profile=profile,
        env=env or {},
        parts=parts,
        should_drop_base_url_fn=should_drop_base_url_fn,
        claude_user_base_url_fn=claude_user_base_url_fn,
    )

    export_statement = render_export_statement(explicit_env)
    if export_statement:
        parts.append(export_statement)
    return "; ".join(parts)


def collect_explicit_api_env(*, profile=None, extra_env: dict[str, str] | None, api_keys: set[str]) -> dict[str, str]:
    explicit_env: dict[str, str] = {}
    if profile is not None:
        explicit_env.update(filtered_api_env(profile.env, api_keys=api_keys))
    if extra_env:
        explicit_env.update(filtered_api_env(extra_env, api_keys=api_keys))
    return explicit_env


def filtered_api_env(env_map: dict[str, str], *, api_keys: set[str]) -> dict[str, str]:
    return {key: value for key, value in env_map.items() if key in api_keys}


def unset_api_env_parts(*, profile=None, api_keys: set[str]) -> list[str]:
    if profile is None or profile.inherit_api:
        return []
    return [f"unset {key}" for key in sorted(api_keys)]


def reconcile_base_url(
    explicit_env: dict[str, str],
    *,
    profile=None,
    env: dict[str, str],
    parts: list[str],
    should_drop_base_url_fn,
    claude_user_base_url_fn,
) -> dict[str, str]:
    base_url = explicit_env.get("ANTHROPIC_BASE_URL")
    if base_url:
        if should_drop_base_url_fn(base_url):
            explicit_env.pop("ANTHROPIC_BASE_URL", None)
            ensure_unset(parts, "ANTHROPIC_BASE_URL")
        return explicit_env

    if profile is not None and not profile.inherit_api:
        return explicit_env

    inherited_base_url = inherited_base_url_value(env=env, claude_user_base_url_fn=claude_user_base_url_fn)
    if not inherited_base_url:
        return explicit_env
    if should_drop_base_url_fn(inherited_base_url):
        ensure_unset(parts, "ANTHROPIC_BASE_URL")
        return explicit_env
    explicit_env["ANTHROPIC_BASE_URL"] = inherited_base_url
    return explicit_env


def inherited_base_url_value(*, env: dict[str, str], claude_user_base_url_fn) -> str:
    env_base_url = str(env.get("ANTHROPIC_BASE_URL") or "").strip()
    if env_base_url:
        return env_base_url
    return str(claude_user_base_url_fn() or "").strip()


def ensure_unset(parts: list[str], key: str) -> None:
    statement = f"unset {key}"
    if statement not in parts:
        parts.append(statement)


def render_export_statement(explicit_env: dict[str, str]) -> str:
    exports = " ".join(
        f"{key}={shlex.quote(value)}"
        for key, value in sorted(explicit_env.items())
        if str(value).strip()
    )
    if not exports:
        return ""
    return f"export {exports}"


__all__ = ["build_claude_env_prefix"]
