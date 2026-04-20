from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from provider_backends.claude.session_runtime.auto_transfer import maybe_auto_extract_old_session
from provider_backends.claude.session_runtime.auto_transfer_runtime import state as auto_transfer_state


def test_maybe_auto_extract_old_session_runs_once_per_key(tmp_path: Path, monkeypatch) -> None:
    session_path = tmp_path / 'old-session.json'
    session_path.write_text('{}\n', encoding='utf-8')
    work_dir = tmp_path / 'repo'
    work_dir.mkdir()
    auto_transfer_state.AUTO_TRANSFER_SEEN.clear()

    saved: list[str] = []

    class FakeTransfer:
        def __init__(self, *, max_tokens: int, work_dir: Path):
            assert max_tokens == 8000
            assert work_dir == work_dir

        def extract_conversations(self, *, session_path: Path, last_n: int):
            assert session_path.exists()
            assert last_n == 0
            return SimpleNamespace(conversations=['one'])

        def save_transfer(self, context, fmt: str, provider: str, *, filename: str):
            saved.append(f'{fmt}:{provider}:{filename}:{len(context.conversations)}')

    class ImmediateThread:
        def __init__(self, *, target, daemon: bool):
            self._target = target
            self.daemon = daemon

        def start(self):
            self._target()

    monkeypatch.setitem(sys.modules, 'memory', SimpleNamespace(ContextTransfer=FakeTransfer))
    monkeypatch.setattr(
        'provider_backends.claude.session_runtime.auto_transfer_runtime.service.threading.Thread',
        ImmediateThread,
    )

    maybe_auto_extract_old_session(str(session_path), work_dir)
    maybe_auto_extract_old_session(str(session_path), work_dir)

    assert len(saved) == 1
