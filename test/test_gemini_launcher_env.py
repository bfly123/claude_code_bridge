from __future__ import annotations

from provider_backends.gemini.launcher_runtime.env import build_gemini_env_prefix
from provider_profiles import ResolvedProviderProfile


def test_build_gemini_env_prefix_clears_non_inherited_api_and_exports_filtered_keys() -> None:
    profile = ResolvedProviderProfile(
        provider="gemini",
        agent_name="agent1",
        env={"GEMINI_API_KEY": "profile-key", "OTHER_ENV": "ignored"},
        inherit_api=False,
    )

    prefix = build_gemini_env_prefix(
        profile=profile,
        extra_env={"GOOGLE_API_KEY": "extra-key", "UNRELATED": "ignored"},
    )

    assert "unset GEMINI_API_KEY" in prefix
    assert "unset GOOGLE_API_KEY" in prefix
    assert "OTHER_ENV" not in prefix
    assert "UNRELATED" not in prefix
    assert "export GEMINI_API_KEY=profile-key GOOGLE_API_KEY=extra-key" in prefix
