from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from memory.transfer_runtime import output as transfer_output


def test_transfer_output_submits_via_unified_ask_agent_mode(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_build_context(project, cwd=None):
        del project, cwd
        return SimpleNamespace(project=SimpleNamespace(project_id="proj-1"))

    def fake_submit_agent_target(context, **kwargs):
        del context
        captured["submit"] = kwargs
        return {"job_id": "job_1"}

    monkeypatch.setattr(transfer_output, "build_context", fake_build_context)
    monkeypatch.setattr(transfer_output, "submit_agent_target", fake_submit_agent_target)
    monkeypatch.setattr(
        transfer_output,
        "watch_job",
        lambda context, job_id, out, timeout, emit_output: SimpleNamespace(status="completed", reply="reply"),
    )
    monkeypatch.setattr(transfer_output, "exit_code_for_status", lambda status, reply: 0)

    ok, reply = transfer_output.send_to_agent(
        agent_name="codex",
        formatted="transfer body",
    )

    assert ok is True
    assert reply == "reply"
    assert captured["submit"] == {
        "target": "codex",
        "message": "transfer body",
        "sender": "user",
        "task_id": None,
    }
