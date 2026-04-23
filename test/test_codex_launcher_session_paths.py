from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from provider_backends.codex.launcher_runtime.session_paths import load_resume_session_id, update_runtime_session_payload


def test_load_resume_session_id_prefers_session_field_then_start_cmd(tmp_path: Path) -> None:
    ccb_dir = tmp_path / ".ccb"
    agent_dir = ccb_dir / "agents" / "agent1" / "runtime"
    agent_dir.mkdir(parents=True, exist_ok=True)
    session_file = ccb_dir / ".codex-agent1-session"
    session_file.write_text(json.dumps({"codex_session_id": "sid-1"}), encoding="utf-8")

    spec = SimpleNamespace(name="agent1")

    assert load_resume_session_id(spec, agent_dir) == "sid-1"

    session_file.write_text(json.dumps({"start_cmd": "codex resume sid-2"}), encoding="utf-8")

    assert load_resume_session_id(spec, agent_dir) == "sid-2"


def test_update_runtime_session_payload_writes_runtime_job_markers(tmp_path: Path) -> None:
    runtime_dir = tmp_path / ".ccb" / "agents" / "agent1" / "provider-runtime" / "codex"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    session_file = tmp_path / ".ccb" / ".codex-agent1-session"
    session_file.write_text(json.dumps({"active": True}, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = update_runtime_session_payload(runtime_dir, job_id="job-object-7", job_owner_pid=4567)

    assert payload is not None
    assert payload["job_id"] == "job-object-7"
    assert payload["job_owner_pid"] == 4567
    assert json.loads(session_file.read_text(encoding="utf-8"))["job_id"] == "job-object-7"
    assert json.loads(session_file.read_text(encoding="utf-8"))["job_owner_pid"] == 4567
    assert (runtime_dir / "job.id").read_text(encoding="utf-8").strip() == "job-object-7"
    assert (runtime_dir / "job-owner.pid").read_text(encoding="utf-8").strip() == "4567"
    assert (runtime_dir / "owner.pid").read_text(encoding="utf-8").strip() == "4567"
