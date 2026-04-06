from __future__ import annotations

import json
from pathlib import Path

from provider_backends.codex.comm_runtime import extract_cwd_from_log_file, extract_session_id


def test_extract_cwd_from_log_file_reads_session_meta(tmp_path: Path) -> None:
    log_path = tmp_path / "session.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {
                    "cwd": f"  {tmp_path / 'repo'}  ",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert extract_cwd_from_log_file(log_path) == str(tmp_path / "repo")


def test_extract_session_id_reads_nested_payload_when_filename_has_no_uuid(tmp_path: Path) -> None:
    session_id = "123e4567-e89b-12d3-a456-426614174321"
    log_path = tmp_path / "session.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {
                    "session": {
                        "id": session_id,
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert extract_session_id(log_path) == session_id
