from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cli.models import ParsedCommand
from project.discovery import ProjectDiscoveryError
from project.resolver import ProjectContext, ProjectResolver, bootstrap_project
from storage.paths import PathLayout


@dataclass(frozen=True)
class CliContext:
    command: ParsedCommand
    cwd: Path
    project: ProjectContext
    paths: PathLayout


class CliContextBuilder:
    def __init__(self, resolver: ProjectResolver | None = None):
        self._resolver = resolver or ProjectResolver()

    def build(
        self,
        command: ParsedCommand,
        *,
        cwd: Path | None = None,
        bootstrap_if_missing: bool = False,
    ) -> CliContext:
        current = Path(cwd or Path.cwd()).expanduser()
        explicit_project = Path(command.project).expanduser() if getattr(command, 'project', None) else None
        try:
            project = self._resolver.resolve(
                current,
                explicit_project=explicit_project,
                allow_ancestor_anchor=not bootstrap_if_missing,
            )
        except ProjectDiscoveryError:
            if not bootstrap_if_missing:
                raise
            bootstrap_root = explicit_project or current
            if not bootstrap_root.exists() or not bootstrap_root.is_dir():
                raise
            project = bootstrap_project(bootstrap_root)
        return CliContext(
            command=command,
            cwd=current,
            project=project,
            paths=PathLayout(project.project_root),
        )
