from __future__ import annotations

from pathlib import Path

from provider_backends.claude.resolver_runtime.pathing import normalize_session_binding


def test_normalize_session_binding_backfills_session_id_from_existing_path(tmp_path: Path) -> None:
    project_root = tmp_path / ".claude" / "projects"
    session_path = project_root / "repo" / "sid-1.jsonl"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text("", encoding="utf-8")
    data = {"claude_session_path": str(session_path)}

    normalize_session_binding(data, tmp_path)

    assert data["claude_session_id"] == "sid-1"
