from __future__ import annotations

from types import SimpleNamespace

from provider_core.session_binding_evidence_runtime.validation import session_binding_is_usable


def test_session_binding_is_usable_rejects_failed_ensure_pane() -> None:
    session = SimpleNamespace(
        pane_id='%1',
        terminal='tmux',
        ensure_pane=lambda: (False, 'pane_dead'),
    )

    assert session_binding_is_usable(session, sleep_fn=lambda _: None) is False


def test_session_binding_is_usable_checks_stability_and_ownership(monkeypatch) -> None:
    checks = iter([True, True])

    class Backend:
        def is_alive(self, pane_id: str) -> bool:
            assert pane_id == '%7'
            return next(checks)

    session = SimpleNamespace(
        pane_id='%7',
        terminal='tmux',
        ensure_pane=lambda: (True, '%7'),
    )

    monkeypatch.setattr(
        'provider_core.session_binding_evidence_runtime.validation.session_backend',
        lambda session: Backend(),
    )
    monkeypatch.setattr(
        'provider_core.session_binding_evidence_runtime.validation.inspect_tmux_pane_ownership',
        lambda session, backend, pane_id: SimpleNamespace(is_owned=True),
    )

    assert session_binding_is_usable(session, sleep_fn=lambda _: None) is True
