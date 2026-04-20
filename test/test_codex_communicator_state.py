from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from provider_backends.codex.comm_runtime.communicator_state import initialize_state


def test_initialize_state_populates_runtime_fields(monkeypatch, tmp_path: Path) -> None:
    session_info = {
        "ccb_session_id": "ccb-1",
        "runtime_dir": str(tmp_path / "runtime"),
        "input_fifo": str(tmp_path / "runtime" / "input.fifo"),
        "_session_file": str(tmp_path / ".ccb" / ".codex-session"),
        "pane_title_marker": "agent1",
    }
    comm = SimpleNamespace(_load_session_info=lambda: dict(session_info))
    monkeypatch.setenv("CODEX_TERMINAL", "tmux")
    monkeypatch.setenv("CODEX_SYNC_TIMEOUT", "45")

    initialize_state(
        comm,
        get_pane_id_from_session_fn=lambda info: "%7",
        get_backend_for_session_fn=lambda info: "backend:tmux",
        pane_health_ttl=2.5,
    )

    assert comm.ccb_session_id == "ccb-1"
    assert comm.runtime_dir == Path(session_info["runtime_dir"])
    assert comm.input_fifo == Path(session_info["input_fifo"])
    assert comm.terminal == "tmux"
    assert comm.pane_id == "%7"
    assert comm.backend == "backend:tmux"
    assert comm.timeout == 45
    assert comm.project_session_file == session_info["_session_file"]
    assert comm._pane_health_ttl == 2.5
    assert comm._log_reader is None
    assert comm._log_reader_primed is False


def test_initialize_state_raises_when_session_missing() -> None:
    comm = SimpleNamespace(_load_session_info=lambda: None)

    try:
        initialize_state(
            comm,
            get_pane_id_from_session_fn=lambda info: "",
            get_backend_for_session_fn=lambda info: None,
            pane_health_ttl=0.0,
        )
    except RuntimeError as exc:
        assert "No active Codex session found" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
