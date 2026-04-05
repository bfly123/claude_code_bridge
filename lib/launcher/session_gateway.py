from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class LauncherSessionGateway:
    target_session_store: object
    target_names: tuple[str, ...]
    provider_pane_id_fn: Callable[[str], str]
    resume: bool

    def write_codex_session(
        self,
        runtime: Path,
        tmux_session: str | None,
        input_fifo: Path,
        output_fifo: Path,
        *,
        pane_id: str | None = None,
        pane_title_marker: str | None = None,
        codex_start_cmd: str | None = None,
    ) -> bool:
        return self.target_session_store.write_codex_session(
            runtime,
            tmux_session,
            input_fifo,
            output_fifo,
            pane_id=pane_id,
            pane_title_marker=pane_title_marker,
            codex_start_cmd=codex_start_cmd,
            resume=self.resume,
        )

    def write_gemini_session(
        self,
        runtime: Path,
        tmux_session: str | None,
        *,
        pane_id: str | None = None,
        pane_title_marker: str | None = None,
        start_cmd: str | None = None,
    ) -> bool:
        return self.target_session_store.write_simple_target_session(
            'gemini',
            runtime,
            tmux_session,
            pane_id=pane_id,
            pane_title_marker=pane_title_marker,
            start_cmd=start_cmd,
        )

    def write_opencode_session(
        self,
        runtime: Path,
        tmux_session: str | None,
        *,
        pane_id: str | None = None,
        pane_title_marker: str | None = None,
        start_cmd: str | None = None,
    ) -> bool:
        return self.target_session_store.write_simple_target_session(
            'opencode',
            runtime,
            tmux_session,
            pane_id=pane_id,
            pane_title_marker=pane_title_marker,
            start_cmd=start_cmd,
        )

    def write_droid_session(
        self,
        runtime: Path,
        tmux_session: str | None,
        *,
        pane_id: str | None = None,
        pane_title_marker: str | None = None,
        start_cmd: str | None = None,
    ) -> bool:
        return self.target_session_store.write_droid_session(
            runtime,
            tmux_session,
            pane_id=pane_id,
            pane_title_marker=pane_title_marker,
            start_cmd=start_cmd,
        )

    def sync_cend_registry(self) -> None:
        if 'codex' not in self.target_names or 'claude' not in self.target_names:
            return
        codex_pane_id = self.provider_pane_id_fn('codex')
        claude_pane_id = self.provider_pane_id_fn('claude')
        if codex_pane_id and claude_pane_id:
            self.target_session_store.write_cend_registry(
                claude_pane_id=claude_pane_id,
                codex_pane_id=codex_pane_id,
            )
