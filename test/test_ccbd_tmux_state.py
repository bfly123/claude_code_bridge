from __future__ import annotations

from types import SimpleNamespace

from ccbd.services.health_assessment.tmux_runtime.state import tmux_pane_state


def test_tmux_pane_state_returns_missing_when_pane_is_absent() -> None:
    backend = SimpleNamespace(pane_exists=lambda pane_id: False)

    assert tmux_pane_state(object(), backend, "%1") == "missing"


def test_tmux_pane_state_returns_foreign_when_ownership_mismatches(monkeypatch) -> None:
    backend = SimpleNamespace(pane_exists=lambda pane_id: True)
    monkeypatch.setattr(
        "ccbd.services.health_assessment.tmux_runtime.state.inspect_tmux_pane_ownership",
        lambda session, backend, pane_id: SimpleNamespace(is_owned=False),
    )

    assert tmux_pane_state(object(), backend, "%1") == "foreign"


def test_tmux_pane_state_prefers_tmux_alive_method(monkeypatch) -> None:
    backend = SimpleNamespace(
        pane_exists=lambda pane_id: True,
        is_tmux_pane_alive=lambda pane_id: True,
    )
    monkeypatch.setattr(
        "ccbd.services.health_assessment.tmux_runtime.state.inspect_tmux_pane_ownership",
        lambda session, backend, pane_id: SimpleNamespace(is_owned=True),
    )

    assert tmux_pane_state(object(), backend, "%1") == "alive"
