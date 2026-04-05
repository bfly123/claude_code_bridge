from __future__ import annotations

from launcher.facade.targets import (
    start_opencode_current_pane,
    start_provider_in_current_pane,
    start_shell_current_target,
)


class LauncherCurrentPaneFacadeMixin:
    def _start_gemini_current_pane(self, *, display_label: str | None = None) -> int:
        return start_shell_current_target(
            self,
            "gemini",
            display_label=display_label,
            start_shell_current_target_fn=self._facade_start_shell_current_target_fn,
            build_pane_title_cmd_fn=self._facade_build_pane_title_cmd_fn,
            build_export_path_cmd_fn=self._facade_build_export_path_cmd_fn,
            start_cmd_fn=self.start_command_factory.build_gemini_start_cmd,
            write_session_fn=self.session_gateway.write_gemini_session,
        )

    def _start_opencode_current_pane(self, *, display_label: str | None = None) -> int:
        return start_opencode_current_pane(
            self,
            display_label=display_label,
            start_opencode_current_pane_fn=self._facade_start_opencode_current_pane_fn,
            build_pane_title_cmd_fn=self._facade_build_pane_title_cmd_fn,
            build_export_path_cmd_fn=self._facade_build_export_path_cmd_fn,
            os_module=self._facade_os_module,
            shlex_module=self._facade_shlex_module,
            subprocess_module=self._facade_subprocess_module,
        )

    def _start_droid_current_pane(self, *, display_label: str | None = None) -> int:
        return start_shell_current_target(
            self,
            "droid",
            display_label=display_label,
            start_shell_current_target_fn=self._facade_start_shell_current_target_fn,
            build_pane_title_cmd_fn=self._facade_build_pane_title_cmd_fn,
            build_export_path_cmd_fn=self._facade_build_export_path_cmd_fn,
            start_cmd_fn=self.start_command_factory.build_droid_start_cmd,
            write_session_fn=self.session_gateway.write_droid_session,
        )

    def _start_provider_in_current_pane(self, provider: str, *, display_label: str | None = None) -> int:
        return start_provider_in_current_pane(
            self,
            provider,
            display_label=display_label,
            start_provider_in_current_pane_fn=self._facade_start_provider_in_current_pane_fn,
        )
