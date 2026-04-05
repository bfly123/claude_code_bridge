from __future__ import annotations

from pathlib import Path
import shutil

from launcher.project_helpers import cmd_settings as _cmd_settings_wired
from launcher.project_helpers import detect_terminal_type as _detect_terminal_type_wired
from launcher.project_helpers import normalize_cmd_config as _normalize_cmd_config_wired
from launcher.project_helpers import project_config_dir as _project_config_dir_wired
from launcher.project_helpers import project_session_file as _project_session_file_wired
from launcher.runtime_helpers import default_cmd_start_cmd as _default_cmd_start_cmd_wired
from provider_sessions.files import resolve_project_config_dir
from terminal_runtime import get_shell_type


class LauncherProjectMixin:
    def _project_config_dir(self) -> Path:
        return _project_config_dir_wired(
            self,
            resolve_project_config_dir_fn=resolve_project_config_dir,
        )

    def _project_session_file(self, filename: str) -> Path:
        return _project_session_file_wired(
            self,
            filename,
            resolve_project_config_dir_fn=resolve_project_config_dir,
        )

    def _normalize_cmd_config(self, raw: dict | None) -> dict:
        return _normalize_cmd_config_wired(raw)

    def _cmd_settings(self) -> dict:
        return _cmd_settings_wired(self)

    def _default_cmd_start_cmd(self) -> str:
        return _default_cmd_start_cmd_wired(
            get_shell_type_fn=get_shell_type,
            shutil_module=shutil,
        )

    def _detect_terminal_type(self):
        return _detect_terminal_type_wired(detect_terminal_fn=self._deps.detect_terminal_fn)
