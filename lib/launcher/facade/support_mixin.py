from __future__ import annotations

from launcher.facade.support import (
    clear_codex_log_binding,
    display_label,
    managed_env_overrides,
    provider_env_overrides,
    require_project_config_dir,
    sync_terminal_type_state,
)


class LauncherFacadeSupportMixin:
    def _sync_terminal_type_state(self) -> None:
        sync_terminal_type_state(self)

    def _managed_env_overrides(self) -> dict:
        return managed_env_overrides(self, environ=self._facade_environ)

    def _display_label(self, provider: str, display_label_value: str | None = None) -> str:
        return display_label(provider, display_label_value)

    def _provider_env_overrides(self, provider: str) -> dict:
        return provider_env_overrides(self, provider, environ=self._facade_environ)

    def _require_project_config_dir(self) -> bool:
        return require_project_config_dir(self, stderr=self._facade_stderr)

    def _clear_codex_log_binding(self, data: dict) -> dict:
        return clear_codex_log_binding(data, stderr=self._facade_stderr)
