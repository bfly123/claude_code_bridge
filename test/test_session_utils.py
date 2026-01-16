from __future__ import annotations

from pathlib import Path

from session_utils import find_project_session_file, safe_write_session


def test_find_project_session_file_is_local_only(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    leaf = root / "a" / "b" / "c"
    leaf.mkdir(parents=True)

    session = root / ".codex-session"
    session.write_text("{}", encoding="utf-8")

    found = find_project_session_file(leaf, ".codex-session")
    assert found is None
    assert find_project_session_file(root, ".codex-session") == session


def test_find_project_session_file_prefers_ccb_config(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir(parents=True)

    cfg = root / ".ccb_config"
    cfg.mkdir(parents=True)
    primary = cfg / ".codex-session"
    primary.write_text("{}", encoding="utf-8")

    legacy = root / ".codex-session"
    legacy.write_text("{}", encoding="utf-8")

    assert find_project_session_file(root, ".codex-session") == primary


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
