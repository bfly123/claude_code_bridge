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


def test_write_session_file_skips_stale_codex_resume_binding_without_bound_authority(tmp_path: Path) -> None:
    ccb_dir = tmp_path / ".ccb"
    ccb_dir.mkdir(parents=True, exist_ok=True)
    (ccb_dir / ".codex-agent1-session").write_text(
        json.dumps(
            {
                "codex_session_id": "legacy-sid",
                "codex_session_path": str(tmp_path / "legacy.jsonl"),
                "codex_provider_authority_fingerprint": "fp-1",
                "updated_at": "2026-04-26 00:00:00",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

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
        launch_session_id="ccb-agent1-456",
        provider_payload={
            "codex_home": str(ccb_dir / "provider-profiles" / "agent1" / "codex"),
            "codex_session_root": str(ccb_dir / "provider-profiles" / "agent1" / "codex" / "sessions"),
            "codex_provider_authority_fingerprint": "fp-1",
        },
    )

    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["codex_provider_authority_fingerprint"] == "fp-1"
    assert "codex_session_id" not in data
    assert "codex_session_path" not in data
    assert "updated_at" not in data


def test_write_session_file_preserves_codex_resume_binding_when_bound_authority_matches(tmp_path: Path) -> None:
    ccb_dir = tmp_path / ".ccb"
    ccb_dir.mkdir(parents=True, exist_ok=True)
    (ccb_dir / ".codex-agent1-session").write_text(
        json.dumps(
            {
                "codex_session_id": "bound-sid",
                "codex_session_path": str(tmp_path / "bound.jsonl"),
                "codex_provider_authority_fingerprint": "fp-1",
                "codex_session_authority_fingerprint": "fp-1",
                "updated_at": "2026-04-26 00:00:00",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

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
        launch_session_id="ccb-agent1-789",
        provider_payload={
            "codex_home": str(ccb_dir / "provider-profiles" / "agent1" / "codex"),
            "codex_session_root": str(ccb_dir / "provider-profiles" / "agent1" / "codex" / "sessions"),
            "codex_provider_authority_fingerprint": "fp-1",
        },
    )

    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert data["codex_session_id"] == "bound-sid"
    assert data["codex_session_path"] == str(tmp_path / "bound.jsonl")
    assert data["codex_session_authority_fingerprint"] == "fp-1"
    assert data["updated_at"] == "2026-04-26 00:00:00"
