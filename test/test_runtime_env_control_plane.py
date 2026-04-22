from __future__ import annotations

from runtime_env.control_plane import control_plane_env


def test_control_plane_env_keeps_provider_api_env(monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'openai-key')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://api.example.test/v1')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'anthropic-key')
    monkeypatch.setenv('GEMINI_API_KEY', 'gemini-key')

    env = control_plane_env()

    assert env['OPENAI_API_KEY'] == 'openai-key'
    assert env['OPENAI_BASE_URL'] == 'https://api.example.test/v1'
    assert env['ANTHROPIC_API_KEY'] == 'anthropic-key'
    assert env['GEMINI_API_KEY'] == 'gemini-key'
