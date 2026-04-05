from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from launcher.session.target_registry import (
    upsert_provider_registry,
    write_cend_registry as _write_cend_registry_impl,
)
from launcher.session.target_writes import (
    write_codex_session as _write_codex_session_impl,
    write_droid_session as _write_droid_session_impl,
    write_simple_target_session as _write_simple_target_session_impl,
)


@dataclass
class LauncherTargetSessionStore:
    project_root: Path
    invocation_dir: Path
    ccb_session_id: str
    terminal_type: str | None
    project_session_path_fn: Callable[[str], Path]
    compute_project_id_fn: Callable[[Path], str]
    normalize_path_for_match_fn: Callable[[str], str]
    check_session_writable_fn: Callable[[Path], tuple[bool, str | None, str | None]]
    safe_write_session_fn: Callable[[Path, str], tuple[bool, str | None]]
    read_session_json_fn: Callable[[Path], dict]
    upsert_registry_fn: Callable[[dict], object]
    clear_codex_log_binding_fn: Callable[[dict], dict]

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
        resume: bool = False,
    ) -> bool:
        return _write_codex_session_impl(
            self,
            runtime,
            tmux_session,
            input_fifo,
            output_fifo,
            pane_id=pane_id,
            pane_title_marker=pane_title_marker,
            codex_start_cmd=codex_start_cmd,
            resume=resume,
        )

    def write_simple_target_session(
        self,
        provider: str,
        runtime: Path,
        tmux_session: str | None,
        *,
        pane_id: str | None = None,
        pane_title_marker: str | None = None,
        start_cmd: str | None = None,
        extra_data: dict | None = None,
        extra_registry: dict | None = None,
    ) -> bool:
        return _write_simple_target_session_impl(
            self,
            provider,
            runtime,
            tmux_session,
            pane_id=pane_id,
            pane_title_marker=pane_title_marker,
            start_cmd=start_cmd,
            extra_data=extra_data,
            extra_registry=extra_registry,
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
        return _write_droid_session_impl(
            self,
            runtime,
            tmux_session,
            pane_id=pane_id,
            pane_title_marker=pane_title_marker,
            start_cmd=start_cmd,
        )

    def write_cend_registry(self, *, claude_pane_id: str, codex_pane_id: str | None) -> bool:
        return _write_cend_registry_impl(
            self,
            claude_pane_id=claude_pane_id,
            codex_pane_id=codex_pane_id,
        )

    def _upsert_provider_registry(
        self,
        provider: str,
        *,
        pane_id: str | None,
        pane_title_marker: str | None,
        session_file: Path,
        extra_registry: dict | None = None,
    ) -> None:
        upsert_provider_registry(
            self,
            provider,
            pane_id=pane_id,
            pane_title_marker=pane_title_marker,
            session_file=session_file,
            extra_registry=extra_registry,
        )
