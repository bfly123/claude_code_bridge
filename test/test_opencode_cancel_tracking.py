from __future__ import annotations

from pathlib import Path

from provider_backends.opencode.runtime.cancel_tracking import detect_cancel_event_in_logs, detect_cancelled_since


class _FakeReader:
    @staticmethod
    def _extract_text(parts: list[dict], allow_reasoning_fallback: bool = True) -> str:
        return "".join(str(part.get("text") or "") for part in parts)

    @staticmethod
    def _extract_req_id_from_text(text: str) -> str | None:
        prefix = "CCB_REQ_ID:"
        if prefix not in text:
            return None
        return text.split(prefix, 1)[1].strip().lower()


def test_detect_cancelled_since_matches_aborted_assistant_for_req_id(monkeypatch) -> None:
    from provider_backends.opencode.runtime.cancel_tracking_runtime import message_cancel

    reader = _FakeReader()
    previous_state = {
        "assistant_count": 1,
        "last_assistant_id": "asst-1",
        "last_assistant_completed": None,
    }
    new_state = {
        "session_id": "ses-demo",
        "last_assistant_id": "asst-2",
        "last_assistant_completed": None,
    }
    messages = [
        {"id": "asst-1", "role": "assistant"},
        {
            "id": "asst-2",
            "role": "assistant",
            "error": {"name": "AbortedError"},
            "parentID": "msg-user-2",
        },
    ]

    monkeypatch.setattr(message_cancel, "capture_state", lambda reader_obj: new_state)
    monkeypatch.setattr(message_cancel, "read_messages", lambda reader_obj, session_id: messages)
    monkeypatch.setattr(
        message_cancel,
        "read_parts",
        lambda reader_obj, message_id: [{"type": "text", "text": "CCB_REQ_ID: req_demo"}],
    )

    cancelled, returned_state = detect_cancelled_since(reader, previous_state, req_id="REQ_DEMO")

    assert cancelled is True
    assert returned_state == new_state


def test_detect_cancel_event_in_logs_switches_to_newer_log_file(tmp_path: Path, monkeypatch) -> None:
    from provider_backends.opencode.runtime.cancel_tracking_runtime import log_cursor

    old_log = tmp_path / "old.log"
    new_log = tmp_path / "new.log"
    old_log.write_text("INFO 2026-04-05T11:00:00 idle\n", encoding="utf-8")
    new_log.write_text(
        "INFO 2026-04-05T11:00:05 path=/session/ses-demo/abort something\n",
        encoding="utf-8",
    )
    old_stat = old_log.stat()
    new_stat = new_log.stat()
    old_mtime = min(old_stat.st_mtime, new_stat.st_mtime)
    new_mtime = max(old_stat.st_mtime, new_stat.st_mtime) + 5
    old_log.touch()
    new_log.touch()
    monkeypatch.setattr(log_cursor, "latest_opencode_log_file", lambda: new_log)
    monkeypatch.setattr(log_cursor, "_safe_stat_mtime", lambda path: new_mtime if path == new_log else old_mtime)
    cursor = {"path": str(old_log), "offset": 0, "mtime": old_mtime}

    matched, new_cursor = detect_cancel_event_in_logs(cursor, session_id="ses-demo", since_epoch_s=0.0)

    assert matched is True
    assert new_cursor["path"] == str(new_log)
    assert int(new_cursor["offset"]) == int(new_log.stat().st_size)
