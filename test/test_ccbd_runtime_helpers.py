from __future__ import annotations

import json
from pathlib import Path

import pytest

import ccbd.runtime as runtime


def test_run_dir_prefers_ccb_run_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CCB_RUN_DIR", str(tmp_path / "custom-run"))

    assert runtime.run_dir() == tmp_path / "custom-run"


def test_state_and_log_paths_append_default_suffixes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CCB_RUN_DIR", str(tmp_path / "run"))

    assert runtime.state_file_path("ccbd") == tmp_path / "run" / "ccbd.json"
    assert runtime.log_path("ccbd") == tmp_path / "run" / "ccbd.log"


def test_get_daemon_work_dir_reads_state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CCB_RUN_DIR", str(tmp_path / "run"))
    state_path = runtime.state_file_path("ccbd")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"work_dir": str(tmp_path / "repo")}), encoding="utf-8")

    assert runtime.get_daemon_work_dir("ccbd") == tmp_path / "repo"


def test_normalize_connect_host_maps_wildcards() -> None:
    assert runtime.normalize_connect_host("") == "127.0.0.1"
    assert runtime.normalize_connect_host("0.0.0.0") == "127.0.0.1"
    assert runtime.normalize_connect_host("::") == "::1"
    assert runtime.normalize_connect_host("[::]") == "::1"
    assert runtime.normalize_connect_host("example.com") == "example.com"


def test_write_log_shrinks_large_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CCB_LOG_MAX_BYTES", "32")
    monkeypatch.setenv("CCB_LOG_SHRINK_CHECK_INTERVAL_S", "0")
    log_path = tmp_path / "ccbd.log"
    log_path.write_bytes(b"x" * 128)

    runtime.write_log(log_path, "tail-line")

    assert log_path.exists()
    assert log_path.stat().st_size <= 64
    assert log_path.read_text(encoding="utf-8").endswith("tail-line\n")
