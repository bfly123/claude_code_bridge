from __future__ import annotations

import os
from pathlib import Path

from provider_backends.gemini.comm_runtime.project_hash_runtime.candidates import get_project_hash, project_hash_candidates


def test_project_hash_candidates_prioritize_newest_matching_project_dir(tmp_path: Path) -> None:
    work_dir = tmp_path / "demo"
    root = tmp_path / "gemini-root"
    work_dir.mkdir()
    root.mkdir()

    older = root / "demo"
    newer = root / "demo-2"
    older_chats = older / "chats"
    newer_chats = newer / "chats"
    older_chats.mkdir(parents=True)
    newer_chats.mkdir(parents=True)
    old_session = older_chats / "session-old.json"
    new_session = newer_chats / "session-new.json"
    old_session.write_text("{}", encoding="utf-8")
    new_session.write_text("{}", encoding="utf-8")
    os.utime(old_session, (10, 10))
    os.utime(new_session, (20, 20))

    candidates = project_hash_candidates(work_dir, root=root)

    assert candidates[:2] == ["demo-2", "demo"]
    assert get_project_hash(work_dir, root=root) == "demo-2"
