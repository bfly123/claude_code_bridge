from __future__ import annotations

import json
from pathlib import Path

import pane_registry_runtime.api as pane_registry
from project.runtime_paths import project_registry_dir


def test_load_registry_by_claude_pane_ignores_flat_legacy_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    work_dir = tmp_path / "proj"
    (work_dir / ".ccb").mkdir(parents=True)
    monkeypatch.chdir(work_dir)

    path = project_registry_dir(work_dir) / "ccb-session-s1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ccb_session_id": "s1",
                "terminal": "tmux",
                "updated_at": 4102444800,
                "claude_pane_id": "%legacy",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    assert pane_registry.load_registry_by_claude_pane("%legacy") is None
