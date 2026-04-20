from __future__ import annotations

from pathlib import Path

from provider_backends.codex.comm_runtime import ask_sync


def test_ask_sync_remembers_log_hint_from_wait_state(tmp_path: Path, capsys) -> None:
    wait_log = tmp_path / "wait.jsonl"

    class _Reader:
        def wait_for_message(self, state, timeout):
            del state, timeout
            return "reply ok", {"log_path": wait_log}

        def current_log_path(self):
            return None

    class _Comm:
        timeout = 5
        log_reader = _Reader()

        def __init__(self) -> None:
            self.remembered: list[Path | None] = []

        def _check_session_health_impl(self, *, probe_terminal: bool):
            del probe_terminal
            return True, "ok"

        def _send_message(self, question: str):
            del question
            return "marker", {"log_path": None}

        def _remember_codex_session(self, log_path):
            self.remembered.append(log_path)

    comm = _Comm()

    assert ask_sync(comm, "hello", timeout=3) == "reply ok"
    assert comm.remembered == [wait_log]
    assert "reply ok" in capsys.readouterr().out
