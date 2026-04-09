from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from provider_backends.opencode.runtime.communicator import initialize_state


def test_initialize_state_populates_runtime_fields(monkeypatch, tmp_path: Path) -> None:
    session_info = {
        "ccb_session_id": "ccb-open-1",
        "runtime_dir": str(tmp_path / "runtime"),
        "_session_file": str(tmp_path / ".ccb" / ".opencode-session"),
        "pane_title_marker": "agent5",
        "opencode_session_id": "ses-1",
        "work_dir": str(tmp_path / "workspace"),
    }
    comm = SimpleNamespace(_load_session_info=lambda: dict(session_info))
    published: list[dict[str, object]] = []
    monkeypatch.setenv("OPENCODE_TERMINAL", "tmux")
    monkeypatch.setenv("OPENCODE_SYNC_TIMEOUT", "45")

    initialize_state(
        comm,
        get_backend_for_session_fn=lambda info: "backend:tmux",
        get_pane_id_from_session_fn=lambda info: "%9",
        log_reader_cls=lambda **kwargs: ("reader", kwargs),
        publish_registry_fn=lambda **kwargs: published.append(kwargs),
    )

    assert comm.ccb_session_id == "ccb-open-1"
    assert comm.runtime_dir == Path(session_info["runtime_dir"])
    assert comm.terminal == "tmux"
    assert comm.pane_id == "%9"
    assert comm.backend == "backend:tmux"
    assert comm.timeout == 45
    assert comm.project_session_file == session_info["_session_file"]
    assert comm.log_reader[0] == "reader"
    assert comm.log_reader[1]["session_id_filter"] == "ses-1"
    assert published and published[0]["ccb_session_id"] == "ccb-open-1"


def test_initialize_state_raises_when_session_missing() -> None:
    comm = SimpleNamespace(_load_session_info=lambda: None)

    try:
        initialize_state(
            comm,
            get_backend_for_session_fn=lambda info: None,
            get_pane_id_from_session_fn=lambda info: "",
            log_reader_cls=lambda **kwargs: None,
            publish_registry_fn=lambda **kwargs: None,
        )
    except RuntimeError as exc:
        assert "No active OpenCode session found" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
