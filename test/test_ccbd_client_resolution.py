from __future__ import annotations

from pathlib import Path

import pytest

from ccbd.client_runtime.resolution import resolve_work_dir, resolve_work_dir_with_registry
from provider_core.runtime_specs import CLAUDE_CLIENT_SPEC, CODEX_CLIENT_SPEC


def _write(path: Path, text: str = "{}") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_resolve_work_dir_uses_project_root_for_ccb_session_file(tmp_path: Path) -> None:
    session_file = _write(tmp_path / ".ccb" / ".claude-session")

    work_dir, resolved = resolve_work_dir(CLAUDE_CLIENT_SPEC, cli_session_file=str(session_file))

    assert work_dir == tmp_path
    assert resolved == session_file.resolve()


def test_resolve_work_dir_rejects_relative_session_file_in_claude_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    _write(tmp_path / ".claude-session")

    with pytest.raises(ValueError, match="absolute path"):
        resolve_work_dir(CLAUDE_CLIENT_SPEC, cli_session_file=".claude-session", default_cwd=tmp_path)


def test_resolve_work_dir_rejects_wrong_filename(tmp_path: Path) -> None:
    wrong = _write(tmp_path / ".wrong-session")

    with pytest.raises(ValueError, match="expected filename"):
        resolve_work_dir(CODEX_CLIENT_SPEC, cli_session_file=str(wrong))


def test_resolve_work_dir_with_registry_finds_project_session_file(tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    workspace = project_root / ".ccb" / "workspaces" / "agent1"
    workspace.mkdir(parents=True, exist_ok=True)
    session_file = _write(project_root / ".ccb" / ".codex-session")

    work_dir, resolved = resolve_work_dir_with_registry(
        CODEX_CLIENT_SPEC,
        provider="codex",
        default_cwd=workspace,
    )

    assert work_dir == workspace
    assert resolved == session_file


def test_resolve_work_dir_with_registry_rejects_registry_only_mode_without_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CCB_REGISTRY_ONLY", "1")

    with pytest.raises(ValueError, match="no longer supported"):
        resolve_work_dir_with_registry(
            CODEX_CLIENT_SPEC,
            provider="codex",
            default_cwd=tmp_path,
        )
