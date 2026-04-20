from __future__ import annotations

from pathlib import Path

from provider_backends.claude.session_runtime.pathing import ensure_work_dir_fields, read_json


def test_ensure_work_dir_fields_backfills_norm_and_project_id(
    monkeypatch,
    tmp_path: Path,
) -> None:
    session_file = tmp_path / ".ccb" / ".claude-session"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {}

    monkeypatch.setattr(
        "provider_backends.claude.session_runtime.pathing.normalize_work_dir",
        lambda work_dir: f"norm::{work_dir}",
    )
    monkeypatch.setattr(
        "provider_backends.claude.session_runtime.pathing.compute_ccb_project_id",
        lambda work_dir: f"proj::{work_dir.name}",
    )

    work_dir = ensure_work_dir_fields(data, session_file=session_file)

    assert work_dir == tmp_path
    assert data["work_dir"] == str(tmp_path)
    assert data["work_dir_norm"] == f"norm::{tmp_path}"
    assert data["ccb_project_id"] == f"proj::{tmp_path.name}"


def test_read_json_returns_none_for_empty_or_invalid_payload(tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    invalid = tmp_path / "invalid.json"
    empty.write_text("{}", encoding="utf-8")
    invalid.write_text("{bad json", encoding="utf-8")

    assert read_json(empty) is None
    assert read_json(invalid) is None
