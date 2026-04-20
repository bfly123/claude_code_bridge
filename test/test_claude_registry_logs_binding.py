from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from provider_backends.claude.registry_support.logs_runtime.binding import refresh_claude_log_binding


class _FakeSession(SimpleNamespace):
    def __init__(
        self,
        *,
        claude_session_path: str = "",
        claude_session_id: str = "",
        work_dir: str,
        data: dict | None = None,
    ) -> None:
        super().__init__(
            claude_session_path=claude_session_path,
            claude_session_id=claude_session_id,
            work_dir=work_dir,
            data=data or {},
        )
        self.binding_updates: list[tuple[Path | None, str | None]] = []

    def update_claude_binding(self, *, session_path: Path | None, session_id: str | None) -> None:
        self.binding_updates.append((session_path, session_id))
        self.claude_session_path = str(session_path) if session_path is not None else ""
        self.claude_session_id = session_id or ""


def test_refresh_claude_log_binding_prefers_intended_resume_log(
    monkeypatch,
    tmp_path: Path,
) -> None:
    work_dir = tmp_path / "repo"
    work_dir.mkdir()
    current = tmp_path / "current.jsonl"
    intended = tmp_path / "intended.jsonl"
    current.write_text("", encoding="utf-8")
    intended.write_text("", encoding="utf-8")
    os.utime(intended, (intended.stat().st_atime, intended.stat().st_mtime + 20))
    session = _FakeSession(
        claude_session_path=str(current),
        claude_session_id="old-id",
        work_dir=str(work_dir),
        data={"start_cmd": "claude --resume wanted-id"},
    )

    monkeypatch.setattr(
        "provider_backends.claude.registry_support.logs_runtime.binding.extract_session_id_from_start_cmd",
        lambda command: "wanted-id" if command else None,
    )
    monkeypatch.setattr(
        "provider_backends.claude.registry_support.logs_runtime.binding.find_log_for_session_id",
        lambda session_id, root: intended,
    )

    updated = refresh_claude_log_binding(session, root=tmp_path, scan_limit=10, force_scan=False)

    assert updated is True
    assert session.binding_updates == [(intended, "wanted-id")]


def test_refresh_claude_log_binding_respects_index_without_forced_scan(
    monkeypatch,
    tmp_path: Path,
) -> None:
    work_dir = tmp_path / "repo"
    work_dir.mkdir()
    current = tmp_path / "current.jsonl"
    index_log = tmp_path / "index.jsonl"
    current.write_text("", encoding="utf-8")
    index_log.write_text("", encoding="utf-8")
    os.utime(current, (current.stat().st_atime, current.stat().st_mtime + 20))
    session = _FakeSession(
        claude_session_path=str(current),
        claude_session_id=index_log.stem,
        work_dir=str(work_dir),
        data={},
    )

    monkeypatch.setattr(
        "provider_backends.claude.registry_support.logs_runtime.binding.extract_session_id_from_start_cmd",
        lambda command: None,
    )
    monkeypatch.setattr(
        "provider_backends.claude.registry_support.logs_runtime.binding.parse_sessions_index",
        lambda work_dir, root: index_log,
    )
    monkeypatch.setattr(
        "provider_backends.claude.registry_support.logs_runtime.binding.scan_latest_log_for_work_dir",
        lambda work_dir, root, scan_limit: (_ for _ in ()).throw(AssertionError("scan should not run")),
    )

    updated = refresh_claude_log_binding(session, root=tmp_path, scan_limit=10, force_scan=False)

    assert updated is False
    assert session.binding_updates == []


def test_refresh_claude_log_binding_uses_scan_when_forced(
    monkeypatch,
    tmp_path: Path,
) -> None:
    work_dir = tmp_path / "repo"
    work_dir.mkdir()
    current = tmp_path / "current.jsonl"
    index_log = tmp_path / "index.jsonl"
    scanned = tmp_path / "scanned.jsonl"
    current.write_text("", encoding="utf-8")
    index_log.write_text("", encoding="utf-8")
    scanned.write_text("", encoding="utf-8")
    os.utime(current, (current.stat().st_atime, current.stat().st_mtime + 10))
    os.utime(scanned, (scanned.stat().st_atime, scanned.stat().st_mtime + 30))
    session = _FakeSession(
        claude_session_path=str(current),
        claude_session_id=index_log.stem,
        work_dir=str(work_dir),
        data={},
    )

    monkeypatch.setattr(
        "provider_backends.claude.registry_support.logs_runtime.binding.extract_session_id_from_start_cmd",
        lambda command: None,
    )
    monkeypatch.setattr(
        "provider_backends.claude.registry_support.logs_runtime.binding.parse_sessions_index",
        lambda work_dir, root: index_log,
    )
    monkeypatch.setattr(
        "provider_backends.claude.registry_support.logs_runtime.binding.scan_latest_log_for_work_dir",
        lambda work_dir, root, scan_limit: (scanned, "scanned-id"),
    )

    updated = refresh_claude_log_binding(session, root=tmp_path, scan_limit=10, force_scan=True)

    assert updated is True
    assert session.binding_updates == [(scanned, "scanned-id")]
