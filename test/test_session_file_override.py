from __future__ import annotations

from pathlib import Path


def _make_session(tmp_path: Path, filename: str) -> Path:
    root = tmp_path / "proj"
    cfg = root / ".ccb_config"
    cfg.mkdir(parents=True)
    session = cfg / filename
    session.write_text("{}", encoding="utf-8")
    return session


def test_codex_comm_find_session_file_prefers_ccb_session_file(tmp_path: Path, monkeypatch) -> None:
    from codex_comm import CodexCommunicator

    session = _make_session(tmp_path, ".codex-session")
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setenv("CCB_SESSION_FILE", str(session))

    comm = object.__new__(CodexCommunicator)
    assert comm._find_session_file() == session


def test_codex_comm_find_session_file_ignores_wrong_filename(tmp_path: Path, monkeypatch) -> None:
    from codex_comm import CodexCommunicator

    session = _make_session(tmp_path, ".gemini-session")
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setenv("CCB_SESSION_FILE", str(session))

    comm = object.__new__(CodexCommunicator)
    assert comm._find_session_file() is None


def test_gemini_comm_find_session_file_prefers_ccb_session_file(tmp_path: Path, monkeypatch) -> None:
    from gemini_comm import GeminiCommunicator

    session = _make_session(tmp_path, ".gemini-session")
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setenv("CCB_SESSION_FILE", str(session))

    comm = object.__new__(GeminiCommunicator)
    assert comm._find_session_file() == session


def test_opencode_comm_find_session_file_prefers_ccb_session_file(tmp_path: Path, monkeypatch) -> None:
    from opencode_comm import OpenCodeCommunicator

    session = _make_session(tmp_path, ".opencode-session")
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setenv("CCB_SESSION_FILE", str(session))

    comm = object.__new__(OpenCodeCommunicator)
    assert comm._find_session_file() == session

