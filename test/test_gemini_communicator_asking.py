from __future__ import annotations

from pathlib import Path

from provider_backends.gemini.comm_runtime.communicator_runtime import ask_sync


def test_gemini_ask_sync_remembers_session_path_from_wait_state(tmp_path: Path, capsys) -> None:
    session_path = tmp_path / "session.json"

    class _Reader:
        def wait_for_message(self, state, timeout):
            del state, timeout
            return "gemini ok", {"session_path": session_path}

    class _Comm:
        timeout = 5
        log_reader = _Reader()

        def __init__(self) -> None:
            self.remembered: list[Path] = []

        def _check_session_health_impl(self, *, probe_terminal: bool):
            del probe_terminal
            return True, "ok"

        def _send_message(self, question: str):
            del question
            return "marker", {}

        def _remember_gemini_session(self, path: Path) -> None:
            self.remembered.append(path)

    comm = _Comm()

    assert ask_sync(comm, "hello", timeout=3) == "gemini ok"
    assert comm.remembered == [session_path]
    assert "gemini ok" in capsys.readouterr().out
