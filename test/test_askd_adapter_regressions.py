from __future__ import annotations

import threading
from pathlib import Path

from askd.adapters.base import ProviderRequest, QueuedTask
from askd.adapters.codex import CodexAdapter
from askd.adapters.gemini import GeminiAdapter
from askd.adapters.opencode import OpenCodeAdapter


class _FakeSession:
    def __init__(self, work_dir: Path, data: dict) -> None:
        self.work_dir = str(work_dir)
        self.data = data
        self.codex_session_path = ""
        self.codex_session_id = ""
        self.gemini_session_path = ""

    def ensure_pane(self):
        return True, "%1"


class _FakeBackend:
    def is_alive(self, pane_id: str) -> bool:
        return True

    def send_text(self, pane_id: str, text: str) -> None:
        return None


class _FakeOpenCodeSession:
    def __init__(self, work_dir: Path) -> None:
        self.work_dir = str(work_dir)
        self.data = {"terminal": "tmux"}
        self.opencode_session_id_filter = None

    def ensure_pane(self):
        return True, "%1"

    def update_opencode_binding(self, *, session_id=None, project_id=None):
        return None


def _task(provider: str, work_dir: Path, timeout_s: float = 3.0) -> QueuedTask:
    req = ProviderRequest(
        client_id=f"{provider}-client",
        work_dir=str(work_dir),
        timeout_s=timeout_s,
        quiet=True,
        message="hello",
        caller=provider,
    )
    return QueuedTask(
        request=req,
        created_ms=0,
        req_id="20260304-000000-001-1-1",
        done_event=threading.Event(),
    )


def test_codex_adapter_dedupes_cumulative_snapshots(tmp_path: Path, monkeypatch) -> None:
    """Repeated/cumulative assistant snapshots should not duplicate final reply."""
    session = _FakeSession(tmp_path, {"terminal": "tmux"})
    backend = _FakeBackend()

    class _Reader:
        def __init__(self, *args, **kwargs):
            self.events = [
                ("user", "CCB_REQ_ID: 20260304-000000-001-1-1"),
                ("assistant", "Part 1"),
                ("assistant", "Part 1"),
                ("assistant", "Part 1\nPart 2"),
                ("assistant", "Part 1\nPart 2\nCCB_DONE: 20260304-000000-001-1-1"),
            ]
            self.idx = 0

        def capture_state(self):
            return {"log_path": None, "offset": 0}

        def wait_for_event(self, state, timeout):
            if self.idx >= len(self.events):
                return None, state
            event = self.events[self.idx]
            self.idx += 1
            return event, state

        def current_log_path(self):
            return None

    monkeypatch.setattr("askd.adapters.codex.load_project_session", lambda _wd: session)
    monkeypatch.setattr("askd.adapters.codex.get_backend_for_session", lambda _data: backend)
    monkeypatch.setattr("askd.adapters.codex.CodexLogReader", _Reader)
    monkeypatch.setattr("askd.adapters.codex.notify_completion", lambda **kwargs: None)

    result = CodexAdapter().handle_task(_task("codex", tmp_path))
    assert result.exit_code == 0
    assert result.done_seen is True
    assert result.reply == "Part 1\nPart 2"


def test_gemini_adapter_negative_timeout_has_safety_deadline(tmp_path: Path, monkeypatch) -> None:
    """timeout_s=-1 should still exit instead of waiting forever."""
    session = _FakeSession(tmp_path, {"terminal": "tmux"})
    backend = _FakeBackend()

    class _Reader:
        def __init__(self, *args, **kwargs):
            pass

        def set_preferred_session(self, _path):
            return None

        def capture_state(self):
            return {"session_path": None, "msg_count": 0}

        def wait_for_message(self, state, timeout):
            return None, state

    monkeypatch.setenv("CCB_GASKD_MAX_WAIT_SECONDS", "1")
    monkeypatch.setattr("askd.adapters.gemini.load_project_session", lambda _wd: session)
    monkeypatch.setattr("askd.adapters.gemini.get_backend_for_session", lambda _data: backend)
    monkeypatch.setattr("askd.adapters.gemini.GeminiLogReader", _Reader)
    monkeypatch.setattr("askd.adapters.gemini.notify_completion", lambda **kwargs: None)

    result = GeminiAdapter().handle_task(_task("gemini", tmp_path, timeout_s=-1.0))
    assert result.exit_code == 2
    assert result.done_seen is False


def test_opencode_adapter_stall_timeout_unblocks_worker(tmp_path: Path, monkeypatch) -> None:
    """If OpenCode produces no output, adapter should fail fast instead of waiting indefinitely."""
    session = _FakeOpenCodeSession(tmp_path)
    backend = _FakeBackend()

    class _Reader:
        def __init__(self, *args, **kwargs):
            pass

        def capture_state(self):
            return {"session_id": "ses_test", "session_updated": 1}

        def wait_for_message(self, state, timeout):
            return None, state

    monkeypatch.setenv("CCB_OASKD_STALL_TIMEOUT_S", "1")
    monkeypatch.setenv("CCB_OASKD_PANE_CHECK_INTERVAL", "0.05")
    monkeypatch.setattr("askd.adapters.opencode.load_project_session", lambda _wd: session)
    monkeypatch.setattr("askd.adapters.opencode.get_backend_for_session", lambda _data: backend)
    monkeypatch.setattr("askd.adapters.opencode.OpenCodeLogReader", _Reader)
    monkeypatch.setattr("askd.adapters.opencode.notify_completion", lambda **kwargs: None)

    result = OpenCodeAdapter().handle_task(_task("opencode", tmp_path, timeout_s=-1.0))
    assert result.exit_code == 2
    assert result.done_seen is False
    assert "stalled" in result.reply.lower()
