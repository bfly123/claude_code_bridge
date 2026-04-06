from __future__ import annotations

from pathlib import Path

from memory.transfer_runtime.auto_transfer_runtime import service as auto_transfer_service
from memory.transfer_runtime.auto_transfer_runtime import state as auto_transfer_state


def test_maybe_auto_transfer_starts_once_for_same_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('CCB_CTX_TRANSFER_ON_SESSION_SWITCH', '1')
    auto_transfer_state.AUTO_TRANSFER_SEEN.clear()

    started: list[dict[str, object]] = []
    monkeypatch.setattr(
        auto_transfer_service,
        'start_transfer_thread',
        lambda **kwargs: started.append(kwargs),
    )

    session_path = tmp_path / 'session.json'
    auto_transfer_service.maybe_auto_transfer(
        provider='codex',
        work_dir=tmp_path,
        session_path=session_path,
        session_id='session-1',
        project_id='proj-1',
    )
    auto_transfer_service.maybe_auto_transfer(
        provider='codex',
        work_dir=tmp_path,
        session_path=session_path,
        session_id='session-1',
        project_id='proj-1',
    )

    assert len(started) == 1
    assert started[0]['provider'] == 'codex'
    assert started[0]['work_dir'] == tmp_path


def test_maybe_auto_transfer_skips_foreign_work_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('CCB_CTX_TRANSFER_ON_SESSION_SWITCH', '1')
    auto_transfer_state.AUTO_TRANSFER_SEEN.clear()

    started: list[dict[str, object]] = []
    monkeypatch.setattr(
        auto_transfer_service,
        'start_transfer_thread',
        lambda **kwargs: started.append(kwargs),
    )

    auto_transfer_service.maybe_auto_transfer(
        provider='codex',
        work_dir=tmp_path / 'other',
        session_path=Path('/tmp/session.json'),
        session_id='session-1',
        project_id='proj-1',
    )

    assert started == []
