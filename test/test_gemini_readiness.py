from __future__ import annotations

from provider_backends.gemini.execution_runtime.start_runtime.readiness import looks_ready, wait_for_runtime_ready


def test_looks_ready_detects_prompt_banner() -> None:
    assert looks_ready("Type your message to Gemini")
    assert not looks_ready("waiting")


def test_wait_for_runtime_ready_returns_after_stable_ready_prompt(monkeypatch) -> None:
    class _Backend:
        def __init__(self) -> None:
            self.calls = 0

        def get_pane_content(self, pane_id: str, *, lines: int = 120) -> str:
            self.calls += 1
            return "Type your message"

    backend = _Backend()
    time_values = iter([0.0, 0.0, 0.5, 0.5, 2.1])

    monkeypatch.setattr(
        "provider_backends.gemini.execution_runtime.start_runtime.readiness.time.time",
        lambda: next(time_values),
    )
    monkeypatch.setattr(
        "provider_backends.gemini.execution_runtime.start_runtime.readiness.time.sleep",
        lambda seconds: None,
    )

    wait_for_runtime_ready(backend, "%1", timeout_s=3.0)

    assert backend.calls == 2
