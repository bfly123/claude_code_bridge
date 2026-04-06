from __future__ import annotations

import json
from pathlib import Path

from provider_core.session_binding_runtime import (
    agent_name_from_session_filename,
    find_bound_session_file,
    resolve_bound_agent_name,
    resolve_bound_instance,
)


def test_find_bound_session_file_uses_workspace_binding_named_agent(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    workspace = tmp_path / "workspace-agent2"
    workspace.mkdir()
    (workspace / ".ccb-workspace.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "record_type": "workspace_binding",
                "target_project": str(project_root),
                "project_id": "demo-project",
                "agent_name": "agent2",
                "workspace_mode": "linked",
                "workspace_path": str(workspace),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    session_file = project_root / ".ccb" / ".gemini-agent2-session"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("{}", encoding="utf-8")

    resolved = find_bound_session_file(
        provider="gemini",
        base_filename=".gemini-session",
        work_dir=workspace,
    )

    assert resolved == session_file


def test_find_bound_session_file_returns_none_when_project_root_is_ambiguous(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    ccb_dir = project_root / ".ccb"
    ccb_dir.mkdir(parents=True, exist_ok=True)
    (ccb_dir / ".gemini-session").write_text("{}", encoding="utf-8")
    (ccb_dir / ".gemini-agent2-session").write_text("{}", encoding="utf-8")

    resolved = find_bound_session_file(
        provider="gemini",
        base_filename=".gemini-session",
        work_dir=project_root,
    )

    assert resolved is None


def test_resolve_bound_agent_name_and_instance_from_named_file() -> None:
    agent_name = agent_name_from_session_filename(
        provider="opencode",
        base_filename=".opencode-session",
        filename=".opencode-agent5-session",
    )
    instance = resolve_bound_instance(
        provider="opencode",
        base_filename=".opencode-session",
        work_dir=Path("/tmp/does-not-matter"),
        allow_env=False,
    )

    assert agent_name == "agent5"
    assert instance is None


def test_agent_name_from_base_session_filename_is_not_treated_as_agent_identity() -> None:
    agent_name = agent_name_from_session_filename(
        provider="codex",
        base_filename=".codex-session",
        filename=".codex-session",
    )

    assert agent_name is None


def test_resolve_bound_agent_name_from_workspace_binding(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    workspace = tmp_path / "workspace-agent4"
    workspace.mkdir()
    (workspace / ".ccb-workspace.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "record_type": "workspace_binding",
                "target_project": str(project_root),
                "project_id": "demo-project",
                "agent_name": "agent4",
                "workspace_mode": "linked",
                "workspace_path": str(workspace),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    agent_name = resolve_bound_agent_name(
        provider="droid",
        base_filename=".droid-session",
        work_dir=workspace,
        allow_env=False,
    )
    instance = resolve_bound_instance(
        provider="droid",
        base_filename=".droid-session",
        work_dir=workspace,
        allow_env=False,
    )

    assert agent_name == "agent4"
    assert instance == "agent4"
