from __future__ import annotations

from launcher.facade.support import build_claude_env, claude_env_overrides
from launcher.facade.targets import start_claude, start_claude_pane


class LauncherClaudeFacadeMixin:
    def _claude_env_overrides(self) -> dict:
        return claude_env_overrides(self, env_builder_cls=self._facade_claude_env_builder_cls)

    def _build_claude_env(self) -> dict:
        return build_claude_env(self, env_builder_cls=self._facade_claude_env_builder_cls)

    def _start_claude(self, *, display_label: str | None = None) -> int:
        return start_claude(
            self,
            display_label=display_label,
            start_claude_fn=self._facade_start_claude_fn,
            translate_fn=self._facade_translate_fn,
            subprocess_module=self._facade_subprocess_module,
        )

    def _start_claude_pane(
        self,
        *,
        parent_pane: str | None,
        direction: str | None,
        display_label: str | None = None,
    ) -> str | None:
        return start_claude_pane(
            self,
            parent_pane=parent_pane,
            direction=direction,
            display_label=display_label,
            start_claude_pane_fn=self._facade_start_claude_pane_fn,
            translate_fn=self._facade_translate_fn,
        )
