from __future__ import annotations

import json

from provider_backends.claude.launcher_runtime.env import build_claude_env_prefix, claude_user_base_url, write_claude_settings_overlay
from provider_profiles.models import ResolvedProviderProfile


def test_build_claude_env_prefix_unsets_dead_local_base_url_from_env() -> None:
    result = build_claude_env_prefix(
        env={"ANTHROPIC_BASE_URL": "http://127.0.0.1:12345"},
        should_drop_base_url_fn=lambda value: value.endswith(":12345"),
        claude_user_base_url_fn=lambda: "",
    )

    assert result == "unset ANTHROPIC_BASE_URL"


def test_build_claude_env_prefix_uses_settings_base_url_when_inheritable() -> None:
    result = build_claude_env_prefix(
        env={},
        should_drop_base_url_fn=lambda value: False,
        claude_user_base_url_fn=lambda: "https://api.example.test",
    )

    assert result == "export ANTHROPIC_BASE_URL=https://api.example.test"


def test_write_claude_settings_overlay_returns_none_without_agent_settings(tmp_path) -> None:
    assert write_claude_settings_overlay(tmp_path, profile=None) is None


def test_write_claude_settings_overlay_strips_env_section_from_agent_settings(tmp_path) -> None:
    profile_root = tmp_path / "profile"
    settings_path = profile_root / "settings.json"
    profile_root.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:12345"},
                "theme": "light",
            }
        ),
        encoding="utf-8",
    )

    overlay = write_claude_settings_overlay(
        tmp_path,
        profile=ResolvedProviderProfile(
            provider='claude',
            agent_name='agent1',
            mode='inherit',
            profile_root=str(profile_root),
        ),
    )

    assert overlay is not None
    payload = json.loads(overlay.read_text(encoding="utf-8"))
    assert payload == {"theme": "light"}
    assert claude_user_base_url(user_settings_path=settings_path) == "http://127.0.0.1:12345"
