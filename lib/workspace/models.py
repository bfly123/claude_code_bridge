from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agents.models import WorkspaceMode, normalize_agent_name

SCHEMA_VERSION = 2


@dataclass(frozen=True)
class WorkspacePlan:
    project_id: str
    project_root: Path
    project_slug: str
    agent_name: str
    workspace_mode: WorkspaceMode
    workspace_path: Path
    binding_path: Path | None
    source_root: Path
    branch_name: str | None
    branch_template: str | None
    unsafe_shared_workspace: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, 'project_root', Path(self.project_root).expanduser().resolve())
        object.__setattr__(self, 'workspace_path', Path(self.workspace_path).expanduser().resolve())
        object.__setattr__(self, 'source_root', Path(self.source_root).expanduser().resolve())
        if self.binding_path is not None:
            object.__setattr__(self, 'binding_path', Path(self.binding_path).expanduser().resolve())
        object.__setattr__(self, 'agent_name', normalize_agent_name(self.agent_name))


@dataclass(frozen=True)
class WorkspaceRef:
    workspace_mode: WorkspaceMode
    workspace_path: Path
    binding_path: Path | None
    branch_name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'workspace_path', Path(self.workspace_path).expanduser().resolve())
        if self.binding_path is not None:
            object.__setattr__(self, 'binding_path', Path(self.binding_path).expanduser().resolve())


@dataclass(frozen=True)
class WorkspaceBinding:
    target_project: str
    project_id: str
    agent_name: str
    workspace_mode: WorkspaceMode
    workspace_path: str
    branch_name: str | None = None
    schema_version: int = SCHEMA_VERSION
    record_type: str = 'workspace_binding'

    def __post_init__(self) -> None:
        object.__setattr__(self, 'agent_name', normalize_agent_name(self.agent_name))

    def to_record(self) -> dict:
        return {
            'schema_version': self.schema_version,
            'record_type': self.record_type,
            'target_project': self.target_project,
            'project_id': self.project_id,
            'agent_name': self.agent_name,
            'workspace_mode': self.workspace_mode.value,
            'workspace_path': self.workspace_path,
            'branch_name': self.branch_name,
        }


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    diagnostics: dict[str, str] = field(default_factory=dict)
