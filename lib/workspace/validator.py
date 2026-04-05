from __future__ import annotations

from pathlib import Path

from agents.models import WorkspaceMode
from workspace.binding import WorkspaceBindingStore
from workspace.models import ValidationResult, WorkspacePlan


class WorkspaceValidator:
    def __init__(self, binding_store: WorkspaceBindingStore | None = None) -> None:
        self._binding_store = binding_store or WorkspaceBindingStore()

    def validate(self, plan: WorkspacePlan) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        diagnostics: dict[str, str] = {
            'workspace_path': str(plan.workspace_path),
            'workspace_mode': plan.workspace_mode.value,
        }

        if plan.workspace_mode is WorkspaceMode.INPLACE:
            if plan.workspace_path != plan.project_root:
                errors.append('inplace workspace_path must equal project_root')
            if not plan.unsafe_shared_workspace:
                errors.append('inplace mode must be marked unsafe_shared_workspace')
        else:
            if plan.workspace_path == plan.project_root:
                errors.append('non-inplace workspace must not reuse project_root')

        if plan.branch_name is None and plan.workspace_mode is WorkspaceMode.GIT_WORKTREE:
            errors.append('git-worktree mode requires branch_name')

        if plan.workspace_path.exists() and plan.binding_path is not None:
            if not plan.binding_path.exists():
                warnings.append('workspace binding file is missing')
            else:
                binding = self._binding_store.load(plan.binding_path)
                if Path(binding.target_project).expanduser().resolve() != plan.project_root:
                    errors.append('workspace binding target_project does not match project_root')
                if binding.project_id != plan.project_id:
                    errors.append('workspace binding project_id does not match project_id')
                if Path(binding.workspace_path).expanduser().resolve() != plan.workspace_path:
                    errors.append('workspace binding workspace_path does not match workspace_path')
                if binding.agent_name != plan.agent_name:
                    errors.append('workspace binding agent_name does not match agent_name')

        return ValidationResult(ok=not errors, errors=tuple(errors), warnings=tuple(warnings), diagnostics=diagnostics)
