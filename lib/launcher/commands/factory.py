from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from launcher.commands.providers.codex import build_codex_start_cmd as _build_codex_start_cmd_impl
from launcher.commands.providers.codex import ensure_codex_auto_approval as _ensure_codex_auto_approval_impl
from launcher.commands.providers.codex import get_latest_codex_session_id as _get_latest_codex_session_id_impl
from launcher.commands.providers.droid import build_droid_start_cmd as _build_droid_start_cmd_impl
from launcher.commands.providers.droid import get_latest_droid_session_id as _get_latest_droid_session_id_impl
from launcher.commands.providers.gemini import build_gemini_start_cmd as _build_gemini_start_cmd_impl
from launcher.commands.providers.gemini import get_latest_gemini_project_hash as _get_latest_gemini_project_hash_impl
from launcher.commands.providers.opencode import build_opencode_start_cmd as _build_opencode_start_cmd_impl
from launcher.commands.providers.opencode import ensure_opencode_auto_config as _ensure_opencode_auto_config_impl
from launcher.commands.providers.opencode import opencode_resume_allowed as _opencode_resume_allowed_impl


@dataclass
class LauncherStartCommandFactory:
    project_root: Path
    invocation_dir: Path
    resume: bool
    auto: bool
    project_session_path_fn: Callable[[str], Path]
    normalize_path_for_match_fn: Callable[[str], str]
    normpath_within_fn: Callable[[str, str], bool]
    build_cd_cmd_fn: Callable[[Path], str]
    translate_fn: Callable[..., str]

    def get_latest_codex_session_id(self) -> tuple[str | None, bool]:
        return _get_latest_codex_session_id_impl(self)

    def ensure_codex_auto_approval(self) -> None:
        _ensure_codex_auto_approval_impl()

    def build_codex_start_cmd(self) -> str:
        return _build_codex_start_cmd_impl(self)

    def get_latest_gemini_project_hash(self) -> tuple[str | None, bool, Path | None]:
        return _get_latest_gemini_project_hash_impl(self)

    def build_gemini_start_cmd(self) -> str:
        return _build_gemini_start_cmd_impl(self)

    def opencode_resume_allowed(self) -> bool:
        return _opencode_resume_allowed_impl(self)

    def ensure_opencode_auto_config(self) -> None:
        _ensure_opencode_auto_config_impl()

    def build_opencode_start_cmd(self) -> str:
        return _build_opencode_start_cmd_impl(self)

    def get_latest_droid_session_id(self) -> tuple[str | None, bool, Path | None]:
        return _get_latest_droid_session_id_impl(self)

    def build_droid_start_cmd(self) -> str:
        return _build_droid_start_cmd_impl(self)

    def get_start_cmd(self, provider: str) -> str:
        builders = {
            "codex": self.build_codex_start_cmd,
            "gemini": self.build_gemini_start_cmd,
            "opencode": self.build_opencode_start_cmd,
            "droid": self.build_droid_start_cmd,
        }
        builder = builders.get(provider)
        if builder is None:
            return ""
        return builder()
