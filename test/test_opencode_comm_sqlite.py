from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _init_opencode_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE message (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                time_created INTEGER NOT NULL,
                time_updated INTEGER NOT NULL,
                data TEXT NOT NULL
            );
            CREATE TABLE part (
                id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                time_created INTEGER NOT NULL,
                time_updated INTEGER NOT NULL,
                data TEXT NOT NULL
            );
            """
        )


def test_opencode_log_reader_reads_messages_and_parts_from_sqlite(tmp_path: Path) -> None:
    from opencode_comm import OpenCodeLogReader

    root = tmp_path / "storage"
    root.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "opencode.db"
    _init_opencode_db(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO message (id, session_id, time_created, time_updated, data) VALUES (?, ?, ?, ?, ?)",
            (
                "msg_sqlite",
                "ses_sqlite",
                1700000000123,
                1700000000999,
                json.dumps({"role": "assistant"}, ensure_ascii=True),
            ),
        )
        conn.execute(
            "INSERT INTO part (id, message_id, session_id, time_created, time_updated, data) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "prt_sqlite",
                "msg_sqlite",
                "ses_sqlite",
                1700000000222,
                1700000000888,
                json.dumps({"type": "text", "text": "hello from sqlite"}, ensure_ascii=True),
            ),
        )
        conn.commit()

    reader = OpenCodeLogReader(root=root, project_id="proj-test")
    messages = reader._read_messages("ses_sqlite")
    assert len(messages) == 1
    assert messages[0].get("id") == "msg_sqlite"
    assert messages[0].get("sessionID") == "ses_sqlite"
    assert messages[0].get("role") == "assistant"
    assert (messages[0].get("time") or {}).get("created") == 1700000000123

    parts = reader._read_parts("msg_sqlite")
    assert len(parts) == 1
    assert parts[0].get("id") == "prt_sqlite"
    assert parts[0].get("messageID") == "msg_sqlite"
    assert parts[0].get("sessionID") == "ses_sqlite"
    assert parts[0].get("text") == "hello from sqlite"
    assert (parts[0].get("time") or {}).get("start") == 1700000000222


def test_opencode_log_reader_falls_back_to_json_when_sqlite_has_no_matching_rows(tmp_path: Path) -> None:
    from opencode_comm import OpenCodeLogReader

    root = tmp_path / "storage"
    message_dir = root / "message" / "ses_file"
    part_dir = root / "part" / "msg_file"
    message_dir.mkdir(parents=True, exist_ok=True)
    part_dir.mkdir(parents=True, exist_ok=True)

    (message_dir / "msg_file.json").write_text(
        json.dumps(
            {
                "id": "msg_file",
                "sessionID": "ses_file",
                "role": "assistant",
                "time": {"created": 1700000100000, "completed": 1700000100010},
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    (part_dir / "prt_file.json").write_text(
        json.dumps(
            {
                "id": "prt_file",
                "messageID": "msg_file",
                "type": "text",
                "text": "hello from json",
                "time": {"start": 1700000100001},
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    db_path = tmp_path / "opencode.db"
    _init_opencode_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO message (id, session_id, time_created, time_updated, data) VALUES (?, ?, ?, ?, ?)",
            ("msg_other", "ses_other", 1, 2, json.dumps({"role": "assistant"}, ensure_ascii=True)),
        )
        conn.execute(
            "INSERT INTO part (id, message_id, session_id, time_created, time_updated, data) VALUES (?, ?, ?, ?, ?, ?)",
            ("prt_other", "msg_other", "ses_other", 1, 2, json.dumps({"type": "text", "text": "other"}, ensure_ascii=True)),
        )
        conn.commit()

    reader = OpenCodeLogReader(root=root, project_id="proj-test")
    messages = reader._read_messages("ses_file")
    assert len(messages) == 1
    assert messages[0].get("id") == "msg_file"
    assert messages[0].get("sessionID") == "ses_file"

    parts = reader._read_parts("msg_file")
    assert len(parts) == 1
    assert parts[0].get("id") == "prt_file"
    assert parts[0].get("messageID") == "msg_file"
    assert parts[0].get("text") == "hello from json"
