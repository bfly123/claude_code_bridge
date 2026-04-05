from __future__ import annotations

from launcher.facade.targets import (
    start_cmd_pane,
    start_codex_tmux,
    start_provider,
    start_simple_tmux_target,
)


class LauncherTmuxFacadeMixin:
    def _start_provider(
        self,
        provider: str,
        *,
        display_label: str | None = None,
        parent_pane: str | None = None,
        direction: str | None = None,
    ) -> str | None:
        return start_provider(
            self,
            provider,
            display_label=display_label,
            parent_pane=parent_pane,
            direction=direction,
        )

    def _start_codex_tmux(
        self,
        *,
        display_label: str | None = None,
        parent_pane: str | None = None,
        direction: str | None = None,
    ) -> str | None:
        return start_codex_tmux(
            self,
            display_label=display_label,
            parent_pane=parent_pane,
            direction=direction,
            start_codex_tmux_fn=self._facade_start_codex_tmux_fn,
            build_export_path_cmd_fn=self._facade_build_export_path_cmd_fn,
            translate_fn=self._facade_translate_fn,
        )

    def _start_gemini_tmux(
        self,
        *,
        display_label: str | None = None,
        parent_pane: str | None = None,
        direction: str | None = None,
    ) -> str | None:
        return start_simple_tmux_target(
            self,
            "gemini",
            display_label=display_label,
            parent_pane=parent_pane,
            direction=direction,
            start_simple_tmux_target_fn=self._facade_start_simple_tmux_target_fn,
            build_export_path_cmd_fn=self._facade_build_export_path_cmd_fn,
            translate_fn=self._facade_translate_fn,
            start_cmd_fn=self.start_command_factory.build_gemini_start_cmd,
            write_session_fn=self.session_gateway.write_gemini_session,
        )

    def _start_opencode_tmux(
        self,
        *,
        display_label: str | None = None,
        parent_pane: str | None = None,
        direction: str | None = None,
    ) -> str | None:
        return start_simple_tmux_target(
            self,
            "opencode",
            display_label=display_label,
            parent_pane=parent_pane,
            direction=direction,
            start_simple_tmux_target_fn=self._facade_start_simple_tmux_target_fn,
            build_export_path_cmd_fn=self._facade_build_export_path_cmd_fn,
            translate_fn=self._facade_translate_fn,
            start_cmd_fn=self.start_command_factory.build_opencode_start_cmd,
            write_session_fn=self.session_gateway.write_opencode_session,
        )

    def _start_droid_tmux(
        self,
        *,
        display_label: str | None = None,
        parent_pane: str | None = None,
        direction: str | None = None,
    ) -> str | None:
        return start_simple_tmux_target(
            self,
            "droid",
            display_label=display_label,
            parent_pane=parent_pane,
            direction=direction,
            start_simple_tmux_target_fn=self._facade_start_simple_tmux_target_fn,
            build_export_path_cmd_fn=self._facade_build_export_path_cmd_fn,
            translate_fn=self._facade_translate_fn,
            start_cmd_fn=self.start_command_factory.build_droid_start_cmd,
            write_session_fn=self.session_gateway.write_droid_session,
        )

    def _start_cmd_pane(
        self,
        *,
        parent_pane: str | None,
        direction: str | None,
        cmd_settings: dict,
    ) -> str | None:
        return start_cmd_pane(
            self,
            parent_pane=parent_pane,
            direction=direction,
            cmd_settings=cmd_settings,
            start_cmd_pane_fn=self._facade_start_cmd_pane_fn,
            build_pane_title_cmd_fn=self._facade_build_pane_title_cmd_fn,
            build_export_path_cmd_fn=self._facade_build_export_path_cmd_fn,
            build_cd_cmd_fn=self._facade_build_cd_cmd_fn,
        )
