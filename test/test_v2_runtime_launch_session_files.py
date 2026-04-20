from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

from cli.services.runtime_launch_runtime.session_files import write_session_file


def test_write_session_file_persists_ccb_session_id_only(tmp_path: Path) -> None:
    ccb_dir = tmp_path / ".ccb"
    ccb_dir.mkdir(parents=True, exist_ok=True)

    context = SimpleNamespace(
        paths=SimpleNamespace(ccb_dir=ccb_dir),
        project=SimpleNamespace(project_id="proj-1", project_root=tmp_path),
    )
    spec = SimpleNamespace(name="agent1", provider="codex")
    plan = SimpleNamespace(workspace_path=tmp_path / "workspace")
    runtime_dir = ccb_dir / "runtime" / "agent1"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    run_cwd = tmp_path / "workspace"
    run_cwd.mkdir(parents=True, exist_ok=True)

    session_path = write_session_file(
        context=context,
        spec=spec,
        plan=plan,
        runtime_dir=runtime_dir,
        run_cwd=run_cwd,
        pane_id="%7",
        tmux_socket_name="ccb-demo",
        tmux_socket_path=str(ccb_dir / "ccbd" / "tmux.sock"),
        pane_title_marker="CCB-agent1",
        start_cmd="codex",
        launch_session_id="ccb-agent1-123",
        provider_payload={"codex_session_id": "provider-sid"},
    )

    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["ccb_session_id"] == "ccb-agent1-123"
    assert "session_id" not in data
    assert data["codex_session_id"] == "provider-sid"
