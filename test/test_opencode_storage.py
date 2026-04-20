from __future__ import annotations

import sqlite3
from pathlib import Path

from opencode_runtime.storage import OpenCodeStorageAccessor


def test_resolve_opencode_db_path_uses_existing_candidate_and_cache(tmp_path: Path) -> None:
    root = tmp_path / 'storage'
    root.mkdir()
    db_path = tmp_path / 'opencode.db'
    db_path.write_text('', encoding='utf-8')
    storage = OpenCodeStorageAccessor(root)

    first = storage.resolve_opencode_db_path()
    db_path.unlink()
    db_path.write_text('', encoding='utf-8')
    second = storage.resolve_opencode_db_path()

    assert first == db_path
    assert second == db_path


def test_fetch_opencode_db_rows_reads_rows_from_database(tmp_path: Path) -> None:
    root = tmp_path / 'storage'
    root.mkdir()
    db_path = tmp_path / 'opencode.db'
    conn = sqlite3.connect(str(db_path))
    conn.execute('CREATE TABLE session (id TEXT, time_updated INTEGER)')
    conn.execute('INSERT INTO session VALUES (?, ?)', ('sid-1', 7))
    conn.commit()
    conn.close()

    storage = OpenCodeStorageAccessor(root)
    rows = storage.fetch_opencode_db_rows(
        'SELECT id, time_updated FROM session ORDER BY time_updated DESC',
        (),
    )

    assert len(rows) == 1
    assert rows[0]['id'] == 'sid-1'
