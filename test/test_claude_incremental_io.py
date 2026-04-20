from __future__ import annotations

from pathlib import Path

from provider_backends.claude.comm_runtime.incremental_io import read_incremental_jsonl


def test_read_incremental_jsonl_tracks_carry_and_filters_invalid_entries(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    path.write_bytes(b'{"role":"assistant"}\n{"x":')

    entries, state = read_incremental_jsonl(path, 0, b"")

    assert entries == [{"role": "assistant"}]
    assert state["offset"] == path.stat().st_size
    assert state["carry"] == b'{"x":'

    with path.open("ab") as handle:
        handle.write(b'1}\nnot-json\n["skip"]\n{"role":"user"}\n')

    entries, state = read_incremental_jsonl(path, state["offset"], state["carry"])

    assert entries == [{"x": 1}, {"role": "user"}]
    assert state["offset"] == path.stat().st_size
    assert state["carry"] == b""


def test_read_incremental_jsonl_resets_offset_after_rotation(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    path.write_bytes(b'{"rotated":true}\n')

    entries, state = read_incremental_jsonl(path, 999, b"stale")

    assert entries == [{"rotated": True}]
    assert state["offset"] == path.stat().st_size
    assert state["carry"] == b""
