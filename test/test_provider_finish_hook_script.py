from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_provider_finish_hook_writes_claude_completion_event(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    completion_dir = tmp_path / "completion"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        '{"type":"user","message":{"content":"CCB_REQ_ID: 20260331-130805-796-1333224-9"}}\n',
        encoding="utf-8",
    )
    payload = {
        "hook_event_name": "Stop",
        "transcript_path": str(transcript),
        "last_assistant_message": "A3_FIX_13_OK",
        "session_id": "claude-session-1",
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(project_root / "bin" / "ccb-provider-finish-hook"),
            "--provider",
            "claude",
            "--completion-dir",
            str(completion_dir),
            "--agent-name",
            "agent3",
            "--workspace",
            str(workspace),
        ],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    event_path = completion_dir / "events" / "20260331-130805-796-1333224-9.json"
    assert event_path.exists()
    event = json.loads(event_path.read_text(encoding="utf-8"))
    assert event["provider"] == "claude"
    assert event["agent_name"] == "agent3"
    assert event["reply"] == "A3_FIX_13_OK"
    assert event["status"] == "completed"


def test_provider_finish_hook_writes_gemini_failed_event_for_login_required_response(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    completion_dir = tmp_path / "completion"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    req_id = "20260331-130805-796-1333224-10"
    payload = {
        "hook_event_name": "AfterAgent",
        "prompt": f"CCB_REQ_ID: {req_id} Execute the full request from @/tmp/request.md and reply directly.",
        "prompt_response": (
            "Code Assist login required.\n"
            "Attempting to open authentication page in your browser.\n"
            "Otherwise navigate to:\nhttps://accounts.google.com/o/oauth2/v2/auth?... \n"
        ),
        "session_id": "gemini-session-1",
        "finishReason": "STOP",
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(project_root / "bin" / "ccb-provider-finish-hook"),
            "--provider",
            "gemini",
            "--completion-dir",
            str(completion_dir),
            "--agent-name",
            "agent3",
            "--workspace",
            str(workspace),
        ],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    event_path = completion_dir / "events" / f"{req_id}.json"
    assert event_path.exists()
    event = json.loads(event_path.read_text(encoding="utf-8"))
    assert event["provider"] == "gemini"
    assert event["agent_name"] == "agent3"
    assert event["status"] == "failed"
    assert event["reply"].startswith("Code Assist login required.")
    assert event["diagnostics"]["hook_event_name"] == "AfterAgent"
    assert event["diagnostics"]["finish_reason"] == "STOP"
    assert event["diagnostics"]["error_type"] == "provider_api_error"
    assert event["diagnostics"]["error_code"] == "LoginRequired"
    assert "login required" in event["diagnostics"]["error_message"].lower()


def test_provider_finish_hook_accepts_job_id_anchor_from_prompt(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    completion_dir = tmp_path / "completion"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    req_id = "job_06188b28c1db"
    payload = {
        "hook_event_name": "AfterAgent",
        "prompt": f"CCB_REQ_ID: {req_id} Execute the full request from @/tmp/request.md and reply directly.",
        "prompt_response": "job-based reply",
        "session_id": "gemini-session-1",
        "finishReason": "STOP",
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(project_root / "bin" / "ccb-provider-finish-hook"),
            "--provider",
            "gemini",
            "--completion-dir",
            str(completion_dir),
            "--agent-name",
            "agent2",
            "--workspace",
            str(workspace),
        ],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    event_path = completion_dir / "events" / f"{req_id}.json"
    assert event_path.exists()
    event = json.loads(event_path.read_text(encoding="utf-8"))
    assert event["req_id"] == req_id
    assert event["reply"] == "job-based reply"
