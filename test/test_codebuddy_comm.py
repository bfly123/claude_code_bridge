from __future__ import annotations

from pathlib import Path

from ccb_protocol import is_done_text, make_req_id
from codebuddy_comm import CodebuddyLogReader


def _write_pane_log(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_capture_state_returns_offset(tmp_path: Path) -> None:
    log_path = tmp_path / "pane.log"
    _write_pane_log(log_path, "hello world\n")

    reader = CodebuddyLogReader(work_dir=tmp_path, pane_log_path=log_path)
    state = reader.capture_state()

    assert state["pane_log_path"] == log_path
    assert state["offset"] > 0


def test_capture_state_no_log(tmp_path: Path) -> None:
    reader = CodebuddyLogReader(work_dir=tmp_path, pane_log_path=tmp_path / "nonexistent.log")
    state = reader.capture_state()

    assert state["offset"] == 0


def test_latest_message_extracts_assistant_block(tmp_path: Path) -> None:
    req_id = make_req_id()
    log_path = tmp_path / "pane.log"
    content = (
        f"CCB_REQ_ID: {req_id}\n"
        f"This is the reply\n"
        f"CCB_DONE: {req_id}\n"
    )
    _write_pane_log(log_path, content)

    reader = CodebuddyLogReader(work_dir=tmp_path, pane_log_path=log_path)
    message = reader.latest_message()

    assert message is not None
    assert "This is the reply" in message


def test_latest_message_strips_ansi(tmp_path: Path) -> None:
    req_id = make_req_id()
    log_path = tmp_path / "pane.log"
    content = (
        f"CCB_REQ_ID: {req_id}\n"
        f"\x1b[32mcolored text\x1b[0m\n"
        f"CCB_DONE: {req_id}\n"
    )
    _write_pane_log(log_path, content)

    reader = CodebuddyLogReader(work_dir=tmp_path, pane_log_path=log_path)
    message = reader.latest_message()

    assert message is not None
    assert "colored text" in message
    assert "\x1b" not in message


def test_latest_message_returns_none_when_no_log(tmp_path: Path) -> None:
    reader = CodebuddyLogReader(work_dir=tmp_path, pane_log_path=tmp_path / "nonexistent.log")
    assert reader.latest_message() is None


def test_wait_for_message_detects_new_content(tmp_path: Path) -> None:
    req_id = make_req_id()
    log_path = tmp_path / "pane.log"
    _write_pane_log(log_path, "initial content\n")

    reader = CodebuddyLogReader(work_dir=tmp_path, pane_log_path=log_path)
    state = reader.capture_state()

    # Append new content with CCB markers
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"CCB_REQ_ID: {req_id}\nreply text\nCCB_DONE: {req_id}\n")

    message, new_state = reader.wait_for_message(state, timeout=0.5)
    assert message is not None
    assert "reply text" in message
    assert new_state["offset"] > state["offset"]


def test_try_get_message_nonblocking(tmp_path: Path) -> None:
    log_path = tmp_path / "pane.log"
    _write_pane_log(log_path, "content\n")

    reader = CodebuddyLogReader(work_dir=tmp_path, pane_log_path=log_path)
    state = reader.capture_state()

    # No new content - should return None immediately
    message, new_state = reader.try_get_message(state)
    assert message is None


def test_latest_conversations_extracts_pairs(tmp_path: Path) -> None:
    req_id = make_req_id()
    log_path = tmp_path / "pane.log"
    content = (
        f"user prompt here\n"
        f"CCB_REQ_ID: {req_id}\n"
        f"assistant reply here\n"
        f"CCB_DONE: {req_id}\n"
    )
    _write_pane_log(log_path, content)

    reader = CodebuddyLogReader(work_dir=tmp_path, pane_log_path=log_path)
    pairs = reader.latest_conversations(n=1)

    assert len(pairs) >= 1
    user_msg, assistant_msg = pairs[-1]
    assert "assistant reply here" in assistant_msg


def test_wait_for_events_returns_events(tmp_path: Path) -> None:
    req_id = make_req_id()
    log_path = tmp_path / "pane.log"
    _write_pane_log(log_path, "")

    reader = CodebuddyLogReader(work_dir=tmp_path, pane_log_path=log_path)
    state = reader.capture_state()

    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"prompt\nCCB_REQ_ID: {req_id}\nreply\nCCB_DONE: {req_id}\n")

    events, new_state = reader.wait_for_events(state, timeout=0.5)
    assert len(events) > 0
    roles = [role for role, _ in events]
    assert "assistant" in roles


def test_set_pane_log_path(tmp_path: Path) -> None:
    reader = CodebuddyLogReader(work_dir=tmp_path)
    log_path = tmp_path / "custom.log"
    _write_pane_log(log_path, "test\n")

    reader.set_pane_log_path(log_path)
    assert reader._pane_log_path == log_path


def test_log_truncation_resets_offset(tmp_path: Path) -> None:
    """When log is truncated (smaller than offset), offset should reset."""
    log_path = tmp_path / "pane.log"
    _write_pane_log(log_path, "a" * 1000 + "\n")

    reader = CodebuddyLogReader(work_dir=tmp_path, pane_log_path=log_path)
    state = reader.capture_state()
    assert state["offset"] > 500

    # Truncate the log
    _write_pane_log(log_path, "short\n")

    # Should handle truncation gracefully
    message, new_state = reader.try_get_message(state)
    # After truncation, offset resets
    assert new_state["offset"] < state["offset"]


def test_session_file_override_prefers_env(tmp_path: Path, monkeypatch) -> None:
    """CCB_SESSION_FILE env var should be used to find session."""
    from codebuddy_comm import CodebuddyCommunicator

    root = tmp_path / "proj"
    cfg = root / ".ccb"
    cfg.mkdir(parents=True)
    session = cfg / ".codebuddy-session"
    session.write_text("{}", encoding="utf-8")

    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setenv("CCB_SESSION_FILE", str(session))

    comm = object.__new__(CodebuddyCommunicator)
    assert comm._find_session_file() == session


def test_session_file_override_ignores_wrong_filename(tmp_path: Path, monkeypatch) -> None:
    """CCB_SESSION_FILE with wrong filename should be ignored."""
    from codebuddy_comm import CodebuddyCommunicator

    root = tmp_path / "proj"
    cfg = root / ".ccb"
    cfg.mkdir(parents=True)
    session = cfg / ".copilot-session"  # Wrong filename
    session.write_text("{}", encoding="utf-8")

    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setenv("CCB_SESSION_FILE", str(session))

    comm = object.__new__(CodebuddyCommunicator)
    assert comm._find_session_file() is None
