from __future__ import annotations

from pathlib import Path

from provider_sessions.files import find_project_session_file, safe_write_session


def test_find_project_session_file_walks_upward(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    leaf = root / "a" / "b" / "c"
    leaf.mkdir(parents=True)

    session_dir = root / ".ccb"
    session_dir.mkdir()
    session = session_dir / ".codex-session"
    session.write_text("{}", encoding="utf-8")

    found = find_project_session_file(leaf, ".codex-session")
    assert found == session
    assert find_project_session_file(root, ".codex-session") == session


def test_find_project_session_file_prefers_ccb_config(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir(parents=True)

    cfg = root / ".ccb"
    cfg.mkdir(parents=True)
    primary = cfg / ".codex-session"
    primary.write_text("{}", encoding="utf-8")

    legacy = root / ".codex-session"
    legacy.write_text("{}", encoding="utf-8")

    assert find_project_session_file(root, ".codex-session") == primary


def test_find_project_session_file_ignores_legacy_root_session(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    legacy = root / ".codex-session"
    legacy.write_text("{}", encoding="utf-8")

    assert find_project_session_file(root, ".codex-session") is None


def test_find_project_session_file_stops_at_nearest_project_anchor(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    inner = outer / "inner"
    leaf = inner / "src"
    leaf.mkdir(parents=True)

    outer_ccb = outer / ".ccb"
    outer_ccb.mkdir()
    (outer_ccb / ".codex-session").write_text('{"outer":true}', encoding="utf-8")

    inner_ccb = inner / ".ccb"
    inner_ccb.mkdir()

    assert find_project_session_file(leaf, ".codex-session") is None


def test_find_project_session_file_uses_workspace_binding_target_project(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_ccb = project_root / ".ccb"
    project_ccb.mkdir(parents=True)
    session = project_ccb / ".codex-session"
    session.write_text("{}", encoding="utf-8")

    workspace_root = tmp_path / "external-workspace"
    workspace_root.mkdir()
    (workspace_root / ".ccb-workspace.json").write_text(
        '{"target_project": "' + str(project_root.resolve()) + '"}',
        encoding="utf-8",
    )
    leaf = workspace_root / "nested"
    leaf.mkdir()

    assert find_project_session_file(leaf, ".codex-session") == session


def test_find_project_session_file_prefers_workspace_binding_over_workspace_anchor(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_ccb = project_root / ".ccb"
    project_ccb.mkdir(parents=True)
    session = project_ccb / ".opencode-demo-session"
    session.write_text("{}", encoding="utf-8")

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / ".ccb").mkdir()
    (workspace_root / ".ccb" / "ccb.config").write_text("demo:opencode\n", encoding="utf-8")
    (workspace_root / ".ccb-workspace.json").write_text(
        '{"target_project": "' + str(project_root.resolve()) + '"}',
        encoding="utf-8",
    )

    assert find_project_session_file(workspace_root, ".opencode-demo-session") == session


def test_safe_write_session_atomic_write(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    ok, err = safe_write_session(target, '{"hello":"world"}\n')
    assert ok is True
    assert err is None
    assert target.read_text(encoding="utf-8") == '{"hello":"world"}\n'
    assert not target.with_suffix(".tmp").exists()

    ok2, err2 = safe_write_session(target, '{"hello":"again"}\n')
    assert ok2 is True
    assert err2 is None
    assert target.read_text(encoding="utf-8") == '{"hello":"again"}\n'
    assert not target.with_suffix(".tmp").exists()
