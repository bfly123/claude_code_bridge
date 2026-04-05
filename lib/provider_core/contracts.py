from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from agents.models import AgentSpec
from cli.context import CliContext
from cli.models import ParsedStartCommand
from provider_execution.base import ProviderExecutionAdapter
from workspace.models import WorkspacePlan

from .manifests import ProviderManifest


@dataclass(frozen=True)
class ProviderSessionBinding:
    provider: str
    load_session: Callable[[Path, str | None], object | None]
    session_id_attr: str
    session_path_attr: str

    def __post_init__(self) -> None:
        provider = str(self.provider or '').strip().lower()
        if not provider:
            raise ValueError('provider cannot be empty')
        object.__setattr__(self, 'provider', provider)


@dataclass(frozen=True)
class ProviderRuntimeLauncher:
    provider: str
    launch_mode: Literal['simple_tmux', 'codex_tmux']
    build_start_cmd: Callable[[ParsedStartCommand, AgentSpec, Path, str], str]
    build_session_payload: Callable[[CliContext, AgentSpec, WorkspacePlan, Path, Path, str, str, str, dict[str, object]], dict[str, object]]
    prepare_runtime: Callable[[Path], dict[str, object]] | None = None
    post_launch: Callable[[object, str, Path, str, dict[str, object]], None] | None = None
    resolve_run_cwd: Callable[[ParsedStartCommand, AgentSpec, WorkspacePlan, Path, str], Path | str | None] | None = None

    def __post_init__(self) -> None:
        provider = str(self.provider or '').strip().lower()
        if not provider:
            raise ValueError('provider cannot be empty')
        object.__setattr__(self, 'provider', provider)


@dataclass(frozen=True)
class ProviderBackend:
    manifest: ProviderManifest
    execution_adapter: ProviderExecutionAdapter | None = None
    session_binding: ProviderSessionBinding | None = None
    runtime_launcher: ProviderRuntimeLauncher | None = None

    @property
    def provider(self) -> str:
        return self.manifest.provider


__all__ = ['ProviderBackend', 'ProviderRuntimeLauncher', 'ProviderSessionBinding']
