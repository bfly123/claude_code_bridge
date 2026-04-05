from __future__ import annotations

import json
from pathlib import Path

from launcher.cleanup import LauncherCleanupCoordinator


def test_mark_project_sessions_inactive_marks_existing_files(tmp_path: Path) -> None:
    session1 = tmp_path / '.ccb' / '.codex-session'
    session2 = tmp_path / '.ccb' / '.gemini-session'
    session1.parent.mkdir(parents=True, exist_ok=True)
    session1.write_text(json.dumps({'active': True}, ensure_ascii=False), encoding='utf-8')
    session2.write_text(json.dumps({'active': True}, ensure_ascii=False), encoding='utf-8')
    marked: list[str] = []

    coordinator = LauncherCleanupCoordinator(
        ccb_pid=100,
        project_session_paths=(session1, session2, tmp_path / '.ccb' / '.missing'),
        mark_session_inactive_fn=lambda path, **kwargs: marked.append(path.name),
        safe_write_session_fn=lambda path, payload: (True, None),
    )

    coordinator.mark_project_sessions_inactive()

    assert marked == ['.codex-session', '.gemini-session']


def test_shutdown_owned_ccbd_is_safe_noop(tmp_path: Path) -> None:
    coordinator = LauncherCleanupCoordinator(
        ccb_pid=321,
        project_session_paths=(),
        mark_session_inactive_fn=lambda path, **kwargs: None,
        safe_write_session_fn=lambda path, payload: (True, None),
    )

    assert coordinator.shutdown_owned_ccbd() is None
