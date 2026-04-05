from __future__ import annotations

import json
import os
from pathlib import Path

from provider_backends.codex.comm import CodexLogReader


def test_codex_log_reader_keeps_bound_session(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    work_dir = tmp_path / "repo"
    work_dir.mkdir()
    preferred = root / "2026" / "abc-session.jsonl"
    newer = root / "2026" / "other-session.jsonl"
    preferred.parent.mkdir(parents=True)

    meta = json.dumps({"type": "session_meta", "payload": {"cwd": str(work_dir)}}) + "\n"
    preferred.write_text(meta, encoding="utf-8")
    preferred_mtime = preferred.stat().st_mtime
    os.utime(preferred, (preferred_mtime - 30.0, preferred_mtime - 30.0))
    newer.write_text(meta, encoding="utf-8")
    preferred_mtime = preferred.stat().st_mtime
    newer_mtime = newer.stat().st_mtime
    os.utime(preferred, (preferred_mtime - 30.0, preferred_mtime - 30.0))
    os.utime(newer, (newer_mtime, newer_mtime))

    reader = CodexLogReader(
        root=root,
        log_path=preferred,
        session_id_filter="abc",
        work_dir=work_dir,
    )

    assert reader.current_log_path() == preferred


def test_codex_log_reader_follows_newer_workspace_session_when_enabled(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    work_dir = tmp_path / "repo"
    work_dir.mkdir()
    preferred = root / "2026" / "abc-session.jsonl"
    preferred.parent.mkdir(parents=True, exist_ok=True)

    meta = json.dumps({"type": "session_meta", "payload": {"cwd": str(work_dir)}}) + "\n"
    preferred.write_text(meta, encoding="utf-8")

    reader = CodexLogReader(
        root=root,
        log_path=preferred,
        session_id_filter="abc",
        work_dir=work_dir,
        follow_workspace_sessions=True,
    )
    state = reader.capture_state()
    assert state["log_path"] == preferred

    rotated = root / "2026" / "rotated-session.jsonl"
    rotated.write_text(
        meta
        + json.dumps(
            {
                "timestamp": "2026-04-04T10:39:14.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "CCB_REQ_ID: req-rotate\n\nhello"}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rotated_mtime = rotated.stat().st_mtime
    os.utime(rotated, (rotated_mtime + 30.0, rotated_mtime + 30.0))
    state["last_rescan"] = 0.0

    entries, next_state = reader.try_get_entries(state)

    assert entries == []
    assert next_state["log_path"] == rotated
    assert reader.current_log_path() == rotated

    entries, _final_state = reader.try_get_entries(next_state)
    assert len(entries) == 1
    assert entries[0]["role"] == "user"
    assert "CCB_REQ_ID: req-rotate" in entries[0]["text"]


def test_codex_log_reader_replays_first_entries_when_log_appears_after_capture(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    work_dir = tmp_path / "repo"
    work_dir.mkdir()

    reader = CodexLogReader(root=root, work_dir=work_dir)
    state = reader.capture_state()
    assert state["log_path"] is None
    assert state["offset"] == -1

    log_path = root / "2026" / "ccb-codex-session.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"cwd": str(work_dir)}}),
                json.dumps(
                    {
                        "timestamp": "2026-03-24T00:00:00.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "CCB_REQ_ID: req-1\n\nhello"}],
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    entries, next_state = reader.try_get_entries(state)

    assert len(entries) == 1
    assert entries[0]["role"] == "user"
    assert "CCB_REQ_ID: req-1" in entries[0]["text"]
    assert next_state["log_path"] == log_path


def test_codex_execution_reader_factory_enables_workspace_follow(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from provider_execution import codex as codex_adapter_module

    captured: dict[str, object] = {}

    class _Reader:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    class _Session:
        codex_session_path = str(tmp_path / "session.jsonl")
        codex_session_id = "session-old"
        work_dir = str(tmp_path / "repo")

    monkeypatch.setattr(codex_adapter_module, "CodexLogReader", _Reader)

    codex_adapter_module._reader_factory(_Session(), None)

    assert captured["log_path"] == tmp_path / "session.jsonl"
    assert captured["session_id_filter"] == "session-old"
    assert captured["work_dir"] == tmp_path / "repo"
    assert captured["follow_workspace_sessions"] is True


def test_codex_log_reader_matches_wsl_and_windows_style_workdirs(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    log_path = root / "2026" / "wsl-session.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps({"type": "session_meta", "payload": {"cwd": "/mnt/C/Users/alice/repo"}}) + "\n",
        encoding="utf-8",
    )

    reader = CodexLogReader(root=root, work_dir=Path("c:/Users/alice/repo"))

    assert reader.current_log_path() == log_path


def test_resolve_unique_codex_session_target_skips_ambiguous_instances(tmp_path: Path) -> None:
    from provider_backends.codex.comm import _resolve_unique_codex_session_target

    work_dir = tmp_path / "repo"
    config_dir = work_dir / ".ccb"
    config_dir.mkdir(parents=True)
    (config_dir / ".codex-auth-session").write_text("{}", encoding="utf-8")
    (config_dir / ".codex-payment-session").write_text("{}", encoding="utf-8")

    session_file, instance = _resolve_unique_codex_session_target(work_dir)

    assert session_file is None
    assert instance is None


def test_resolve_unique_codex_session_target_accepts_single_instance(tmp_path: Path) -> None:
    from provider_backends.codex.comm import _resolve_unique_codex_session_target

    work_dir = tmp_path / "repo"
    config_dir = work_dir / ".ccb"
    config_dir.mkdir(parents=True)
    target = config_dir / ".codex-auth-session"
    target.write_text("{}", encoding="utf-8")

    session_file, instance = _resolve_unique_codex_session_target(work_dir)

    assert session_file == target
    assert instance == "auth"
