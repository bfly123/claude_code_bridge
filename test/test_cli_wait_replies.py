from __future__ import annotations

from cli.services.wait_runtime.replies import latest_replies


def test_latest_replies_keeps_latest_attempt_per_message_and_latest_reply_per_attempt() -> None:
    payload = {
        "attempts": [
            {"attempt_id": "a1", "message_id": "m1", "agent_name": "agent1", "job_id": "job-old", "retry_index": 0, "updated_at": "2026-04-06T00:00:00Z"},
            {"attempt_id": "a2", "message_id": "m1", "agent_name": "agent1", "job_id": "job-new", "retry_index": 1, "updated_at": "2026-04-06T00:01:00Z"},
        ],
        "replies": [
            {"reply_id": "r1", "attempt_id": "a2", "message_id": "m1", "agent_name": "agent1", "terminal_status": "completed", "notice": False, "finished_at": "2026-04-06T00:02:00Z", "reply": "older"},
            {"reply_id": "r2", "attempt_id": "a2", "message_id": "m1", "agent_name": "agent1", "terminal_status": "completed", "notice": True, "notice_kind": "heartbeat", "finished_at": "2026-04-06T00:03:00Z", "reply": "newer"},
        ],
    }

    attempt_count, replies, terminal_count, notice_count = latest_replies(payload)

    assert attempt_count == 1
    assert terminal_count == 0
    assert notice_count == 1
    assert replies == (
        {
            "reply_id": "r2",
            "message_id": "m1",
            "attempt_id": "a2",
            "agent_name": "agent1",
            "job_id": "job-new",
            "terminal_status": "completed",
            "notice": True,
            "notice_kind": "heartbeat",
            "last_progress_at": None,
            "heartbeat_silence_seconds": None,
            "reason": None,
            "finished_at": "2026-04-06T00:03:00Z",
            "reply": "newer",
        },
    )
