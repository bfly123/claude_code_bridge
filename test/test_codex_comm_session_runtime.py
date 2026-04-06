from __future__ import annotations

from pathlib import Path

import pytest

from provider_backends.codex.comm_runtime import check_tmux_runtime_health


def test_check_tmux_runtime_health_reports_missing_bridge_pid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "codex.pid").write_text("123", encoding="utf-8")
    input_fifo = runtime_dir / "input.fifo"
    input_fifo.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "provider_backends.codex.comm_runtime.session_runtime_runtime.health._probe_pid",
        lambda pid, *, label: (True, f"{label} ok"),
    )

    healthy, status = check_tmux_runtime_health(runtime_dir=runtime_dir, input_fifo=input_fifo)

    assert healthy is False
    assert status == "Bridge process PID file not found"


def test_check_tmux_runtime_health_reports_invalid_codex_pid(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "codex.pid").write_text("bad-pid", encoding="utf-8")
    input_fifo = runtime_dir / "input.fifo"
    input_fifo.write_text("", encoding="utf-8")

    healthy, status = check_tmux_runtime_health(runtime_dir=runtime_dir, input_fifo=input_fifo)

    assert healthy is False
    assert status == "Failed to read Codex process PID"
