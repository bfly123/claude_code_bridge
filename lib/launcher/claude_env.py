from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class LauncherClaudeEnvBuilder:
    target_names: tuple[str, ...]
    runtime_dir: Path
    ccb_session_id: str
    terminal_type: str | None
    provider_env_overrides_fn: Callable[[str], dict]
    provider_pane_id_fn: Callable[[str], str]

    def build_env_overrides(self) -> dict:
        env: dict[str, str] = {}
        env.update(self.provider_env_overrides_fn('claude'))
        env['CCB_SESSION_ID'] = self.ccb_session_id
        for provider in self.target_names:
            if provider == 'claude':
                continue
            self._append_provider_binding(env, provider)
        return env

    def _append_provider_binding(self, env: dict[str, str], provider: str) -> None:
        provider = (provider or '').strip().lower()
        runtime = self.runtime_dir / provider
        pane_id = self.provider_pane_id_fn(provider)
        if provider == 'codex':
            env['CODEX_RUNTIME_DIR'] = str(runtime)
            env['CODEX_INPUT_FIFO'] = str(runtime / 'input.fifo')
            env['CODEX_OUTPUT_FIFO'] = str(runtime / 'output.fifo')
            env['CODEX_TERMINAL'] = self.terminal_type or ''
            self._set_pane_target(env, provider='CODEX', pane_id=pane_id)
            return
        if provider == 'gemini':
            env['GEMINI_RUNTIME_DIR'] = str(runtime)
            env['GEMINI_TERMINAL'] = self.terminal_type or ''
            self._set_pane_target(env, provider='GEMINI', pane_id=pane_id)
            return
        if provider == 'opencode':
            env['OPENCODE_RUNTIME_DIR'] = str(runtime)
            env['OPENCODE_TERMINAL'] = self.terminal_type or ''
            self._set_pane_target(env, provider='OPENCODE', pane_id=pane_id)
            return
        if provider == 'droid':
            env['DROID_RUNTIME_DIR'] = str(runtime)
            env['DROID_TERMINAL'] = self.terminal_type or ''
            self._set_pane_target(env, provider='DROID', pane_id=pane_id)

    def _set_pane_target(self, env: dict[str, str], *, provider: str, pane_id: str) -> None:
        env[f'{provider}_TMUX_SESSION'] = pane_id
