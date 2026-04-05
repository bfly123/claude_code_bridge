from __future__ import annotations

from pathlib import Path

from launcher.bootstrap.app_deps import LauncherAppDeps
from launcher.bootstrap.app_deps import configure_facade_dependencies as _configure_facade_dependencies_impl
from launcher.facade.mixins import LauncherFacadeMixin
from launcher.app_project import LauncherProjectMixin
from launcher.app_runtime import LauncherRuntimeMixin
from launcher.bootstrap.app_wiring import build_core_services as _build_core_services_impl
from launcher.bootstrap.app_wiring import build_launcher_services as _build_launcher_services_impl
from launcher.bootstrap.app_wiring import build_runup_services as _build_runup_services_impl
from launcher.bootstrap.app_wiring import build_store_services as _build_store_services_impl
from launcher.bootstrap.app_wiring import configure_managed_env as _configure_managed_env_impl
from launcher.bootstrap.app_wiring import init_runtime_state as _init_runtime_state_impl


class LauncherApp(LauncherProjectMixin, LauncherRuntimeMixin, LauncherFacadeMixin):
    def __init__(
        self,
        providers: list,
        resume: bool = False,
        auto: bool = False,
        cmd_config: dict | None = None,
        *,
        script_dir: Path,
        version: str,
        supported_client_specs: dict,
        tmux_backend_cls,
        detect_terminal_fn,
        os_module,
        subprocess_module,
        tempfile_module,
        time_module,
        getpass_module,
        shlex_module,
    ) -> None:
        self.target_names = providers or ["codex"]
        self.resume = resume
        self.auto = auto
        self.cmd_config = self._normalize_cmd_config(cmd_config)
        self.script_dir = script_dir
        self.invocation_dir = Path.cwd()
        self._deps = LauncherAppDeps(
            script_dir=script_dir,
            version=version,
            supported_client_specs=supported_client_specs,
            tmux_backend_cls=tmux_backend_cls,
            detect_terminal_fn=detect_terminal_fn,
            os_module=os_module,
            subprocess_module=subprocess_module,
            tempfile_module=tempfile_module,
            time_module=time_module,
            getpass_module=getpass_module,
            shlex_module=shlex_module,
        )
        self._configure_facade_dependencies()
        self._init_runtime_state()
        self._build_core_services()
        self._build_store_services()
        self._build_launcher_services()
        self._build_runup_services()
        self._configure_managed_env()

    def _configure_facade_dependencies(self) -> None:
        _configure_facade_dependencies_impl(self, self._deps)

    def _init_runtime_state(self) -> None:
        _init_runtime_state_impl(self)

    def _build_core_services(self) -> None:
        _build_core_services_impl(self)

    def _build_store_services(self) -> None:
        _build_store_services_impl(self)

    def _build_launcher_services(self) -> None:
        _build_launcher_services_impl(self)

    def _build_runup_services(self) -> None:
        _build_runup_services_impl(self)

    def _configure_managed_env(self) -> None:
        _configure_managed_env_impl(self)
