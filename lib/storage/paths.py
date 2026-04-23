from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from project.ids import compute_project_id, project_slug

from .path_helpers import SocketPlacement, choose_socket_placement
from .paths_agents import (
    AgentMailboxPathMixin,
    AgentRuntimePathMixin,
    WorkspacePathMixin,
)
from .paths_ccbd import (
    CcbdArtifactsPathMixin,
    CcbdMailboxPathMixin,
    CcbdMountPathMixin,
    CcbdOpsPathMixin,
    ProjectAnchorPathMixin,
)
from .paths_targets import TargetPathMixin


@dataclass(frozen=True)
class PathLayout(
    ProjectAnchorPathMixin,
    CcbdMailboxPathMixin,
    CcbdMountPathMixin,
    CcbdOpsPathMixin,
    CcbdArtifactsPathMixin,
    AgentRuntimePathMixin,
    AgentMailboxPathMixin,
    WorkspacePathMixin,
    TargetPathMixin,
):
    project_root: Path

    def __post_init__(self) -> None:
        root = Path(self.project_root).expanduser()
        try:
            root = root.resolve()
        except Exception:
            root = root.absolute()
        object.__setattr__(self, 'project_root', root)

    @property
    def project_slug(self) -> str:
        return project_slug(self.project_root)

    @property
    def project_socket_key(self) -> str:
        return compute_project_id(self.project_root)[:12]

    def _project_socket_placement(self, stem: str) -> SocketPlacement:
        return choose_socket_placement(
            preferred_path=self.ccbd_dir / f'{stem}.sock',
            project_socket_key=self.project_socket_key,
        )

    def _project_socket_path(self, stem: str) -> Path:
        return self._project_socket_placement(stem).effective_path


__all__ = ['PathLayout']
