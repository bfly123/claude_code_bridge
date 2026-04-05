from __future__ import annotations

from datetime import datetime, timezone
import re

from agents.models import AgentSpec, WorkspaceMode
from project.resolver import ProjectContext
from storage.paths import PathLayout
from workspace.models import WorkspacePlan

_PLACEHOLDER_RE = re.compile(r'\{([a-z_]+)\}')
_ALLOWED_BRANCH_VARS = {'agent_name', 'project_slug', 'date'}
_DEFAULT_BRANCH_TEMPLATE = 'ccb/{agent_name}'


class WorkspacePlanner:
    def plan(self, agent_spec: AgentSpec, project_ctx: ProjectContext) -> WorkspacePlan:
        layout = PathLayout(project_ctx.project_root)
        if agent_spec.workspace_mode is WorkspaceMode.INPLACE:
            workspace_path = project_ctx.project_root
            binding_path = None
            unsafe_shared_workspace = True
            branch_name = None
        else:
            workspace_path = layout.workspace_path(agent_spec.name, workspace_root=agent_spec.workspace_root)
            binding_path = layout.workspace_binding_path(agent_spec.name, workspace_root=agent_spec.workspace_root)
            unsafe_shared_workspace = False
            branch_name = self._render_branch_name(agent_spec, layout.project_slug)
            if agent_spec.workspace_mode is WorkspaceMode.COPY:
                branch_name = None

        return WorkspacePlan(
            project_id=project_ctx.project_id,
            project_root=project_ctx.project_root,
            project_slug=layout.project_slug,
            agent_name=agent_spec.name,
            workspace_mode=agent_spec.workspace_mode,
            workspace_path=workspace_path,
            binding_path=binding_path,
            source_root=project_ctx.project_root,
            branch_name=branch_name,
            branch_template=agent_spec.branch_template or _DEFAULT_BRANCH_TEMPLATE,
            unsafe_shared_workspace=unsafe_shared_workspace,
        )

    def _render_branch_name(self, agent_spec: AgentSpec, project_slug: str) -> str:
        template = agent_spec.branch_template or _DEFAULT_BRANCH_TEMPLATE
        variables = set(_PLACEHOLDER_RE.findall(template))
        unknown = sorted(variables - _ALLOWED_BRANCH_VARS)
        if unknown:
            raise ValueError(f'branch_template contains unsupported variables: {unknown}')
        rendered = template.format(
            agent_name=agent_spec.name,
            project_slug=project_slug,
            date=datetime.now(timezone.utc).strftime('%Y%m%d'),
        )
        branch_name = rendered.strip()
        if not branch_name:
            raise ValueError('branch_template rendered empty branch name')
        return branch_name
