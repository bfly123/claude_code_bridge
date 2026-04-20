from __future__ import annotations

import json
import os
from pathlib import Path

from provider_core.protocol import is_done_text
from provider_backends.gemini.comm import GeminiLogReader


def _write_session(path: Path, *, messages: list[dict], session_id: str = "sid-1") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sessionId": session_id, "messages": messages}
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _write_project_root(project_dir: Path, work_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / ".project_root").write_text(str(work_dir.resolve()), encoding="utf-8")


def test_capture_state_finds_slugified_suffix_project_hash(tmp_path: Path) -> None:
    work_dir = tmp_path / "claude_code_bridge"
    work_dir.mkdir()
    root = tmp_path / "gemini-root"
    project_dir = root / "claude-code-bridge-1"
    _write_project_root(project_dir, work_dir)
    session_path = project_dir / "chats" / "session-a.json"
    _write_session(
        session_path,
        messages=[
            {"type": "user", "content": "hello"},
            {"type": "gemini", "id": "g1", "content": "world"},
        ],
    )

    reader = GeminiLogReader(root=root, work_dir=work_dir)
    state = reader.capture_state()

    assert state.get("session_path") == session_path
    assert int(state.get("msg_count") or 0) == 2


def test_wait_for_message_reads_reply_from_slugified_suffix_project_hash(tmp_path: Path) -> None:
    req_id = "20260222-161452-539-76463-1"
    work_dir = tmp_path / "claude_code_bridge"
    work_dir.mkdir()
    root = tmp_path / "gemini-root"
    project_dir = root / "claude-code-bridge-1"
    _write_project_root(project_dir, work_dir)
    session_path = project_dir / "chats" / "session-b.json"

    messages = [{"type": "user", "content": f"CCB_REQ_ID: {req_id}\nquestion"}]
    _write_session(session_path, messages=messages)

    reader = GeminiLogReader(root=root, work_dir=work_dir)
    state = reader.capture_state()

    messages.append({"type": "gemini", "id": "g2", "content": f"ok\nCCB_DONE: {req_id}"})
    _write_session(session_path, messages=messages)

    reply, new_state = reader.wait_for_message(state, timeout=0.5)

    assert reply is not None
    assert is_done_text(reply, req_id)
    assert new_state.get("session_path") == session_path


def test_set_preferred_session_rejects_foreign_project_session(tmp_path: Path) -> None:
    root = tmp_path / "gemini-root"
    work_dir = tmp_path / "project-a"
    other_dir = tmp_path / "project-b"
    work_dir.mkdir()
    other_dir.mkdir()

    own_reader = GeminiLogReader(root=root, work_dir=work_dir)
    own_project_dir = root / own_reader._project_hash
    _write_project_root(own_project_dir, work_dir)
    own_session = own_project_dir / "chats" / "session-own.json"
    _write_session(own_session, messages=[{"type": "gemini", "id": "g1", "content": "own"}], session_id="own")

    other_reader = GeminiLogReader(root=root, work_dir=other_dir)
    foreign_project_dir = root / other_reader._project_hash
    _write_project_root(foreign_project_dir, other_dir)
    foreign_session = foreign_project_dir / "chats" / "session-foreign.json"
    _write_session(
        foreign_session,
        messages=[{"type": "gemini", "id": "g2", "content": "foreign"}],
        session_id="foreign",
    )
    foreign_stat = foreign_session.stat()
    own_stat = own_session.stat()
    os.utime(
        foreign_session,
        (
            max(foreign_stat.st_atime, own_stat.st_atime) + 10,
            max(foreign_stat.st_mtime, own_stat.st_mtime) + 10,
        ),
    )

    reader = GeminiLogReader(root=root, work_dir=work_dir)
    reader.set_preferred_session(foreign_session)

    assert reader._preferred_session is None
    assert reader.current_session_path() == own_session


def test_set_preferred_session_accepts_current_project_session(tmp_path: Path) -> None:
    root = tmp_path / "gemini-root"
    work_dir = tmp_path / "project-a"
    work_dir.mkdir()

    reader = GeminiLogReader(root=root, work_dir=work_dir)
    project_dir = root / reader._project_hash
    _write_project_root(project_dir, work_dir)
    own_session = project_dir / "chats" / "session-own.json"
    _write_session(own_session, messages=[{"type": "gemini", "id": "g1", "content": "own"}], session_id="own")

    reader.set_preferred_session(own_session)

    assert reader._preferred_session == own_session
    assert reader.current_session_path() == own_session


def test_capture_state_ignores_newer_foreign_suffix_dir_when_project_root_differs(tmp_path: Path) -> None:
    root = tmp_path / "gemini-root"
    work_dir = tmp_path / "repo-a" / ".ccb" / "workspaces" / "gemini"
    other_dir = tmp_path / "repo-b" / ".ccb" / "workspaces" / "gemini"
    work_dir.mkdir(parents=True)
    other_dir.mkdir(parents=True)

    own_project_dir = root / "gemini"
    foreign_project_dir = root / "gemini-1"
    _write_project_root(own_project_dir, work_dir)
    _write_project_root(foreign_project_dir, other_dir)

    own_session = own_project_dir / "chats" / "session-own.json"
    foreign_session = foreign_project_dir / "chats" / "session-foreign.json"
    _write_session(own_session, messages=[{"type": "gemini", "id": "g1", "content": "own"}], session_id="own")
    _write_session(foreign_session, messages=[{"type": "gemini", "id": "g2", "content": "foreign"}], session_id="foreign")

    own_stat = own_session.stat()
    os.utime(foreign_session, (own_stat.st_atime + 10, own_stat.st_mtime + 10))

    reader = GeminiLogReader(root=root, work_dir=work_dir)
    state = reader.capture_state()

    assert state.get("session_path") == own_session
