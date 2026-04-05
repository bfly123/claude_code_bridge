from __future__ import annotations

from pathlib import Path

from launcher.claude_env import LauncherClaudeEnvBuilder


def test_claude_env_builder_includes_provider_runtime_bindings_for_tmux(tmp_path: Path) -> None:
    builder = LauncherClaudeEnvBuilder(
        target_names=('claude', 'codex', 'gemini', 'opencode', 'droid'),
        runtime_dir=tmp_path / 'runtime',
        ccb_session_id='ai-1',
        terminal_type='tmux',
        provider_env_overrides_fn=lambda provider: {'CCB_CALLER': provider},
        provider_pane_id_fn=lambda provider: {'codex': '%1', 'gemini': '%2', 'opencode': '%3', 'droid': '%4'}.get(provider, ''),
    )

    env = builder.build_env_overrides()

    assert env['CCB_CALLER'] == 'claude'
    assert env['CCB_SESSION_ID'] == 'ai-1'
    assert env['CODEX_TMUX_SESSION'] == '%1'
    assert env['GEMINI_TMUX_SESSION'] == '%2'
    assert env['OPENCODE_TMUX_SESSION'] == '%3'
    assert env['DROID_TMUX_SESSION'] == '%4'
