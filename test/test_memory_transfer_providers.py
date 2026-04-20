from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from memory.transfer_runtime.providers_runtime import codex as codex_provider
from memory.transfer_runtime.providers_runtime import opencode as opencode_provider
from memory.types import SessionNotFoundError


class _Deduper:
    @staticmethod
    def clean_content(value: str) -> str:
        return value.strip()


class _Formatter:
    @staticmethod
    def truncate_to_limit(pairs, _max_tokens):
        return list(pairs)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text)


def test_extract_from_codex_falls_back_to_latest_log_path(tmp_path: Path, monkeypatch) -> None:
    scan_path = tmp_path / 'latest.jsonl'
    scan_path.write_text('', encoding='utf-8')

    class FakeCodexLogReader:
        def __init__(self, *, log_path, session_id_filter, work_dir):
            self.log_path = log_path
            self.session_id_filter = session_id_filter
            self.work_dir = work_dir

        def _latest_log(self):
            return scan_path

        def latest_conversations(self, fetch_n):
            assert fetch_n == 4
            return [(' user ', ' assistant ')]

    monkeypatch.setattr(
        codex_provider,
        'load_session_data',
        lambda *_args, **_kwargs: (None, {'session_path': str(tmp_path / 'missing.jsonl')}),
    )
    monkeypatch.setitem(
        sys.modules,
        'provider_backends.codex.comm',
        SimpleNamespace(CodexLogReader=FakeCodexLogReader),
    )

    context = codex_provider.extract_from_codex(
        work_dir=tmp_path,
        source_session_files={'codex': '.codex-session'},
        deduper=_Deduper(),
        formatter=_Formatter(),
        max_tokens=200,
        fallback_pairs=4,
        last_n=0,
    )

    assert context.source_provider == 'codex'
    assert context.source_session_id == 'latest'
    assert context.metadata['session_path'] == str(scan_path)
    assert context.conversations == [('user', 'assistant')]


def test_extract_from_opencode_uses_captured_session_state(tmp_path: Path, monkeypatch) -> None:
    session_path = tmp_path / 'session.json'
    session_path.write_text('', encoding='utf-8')

    class FakeOpenCodeLogReader:
        def __init__(self, *, work_dir, project_id, session_id_filter):
            self.work_dir = work_dir
            self.project_id = project_id
            self.session_id_filter = session_id_filter

        def capture_state(self):
            return {'session_id': '', 'session_path': str(session_path)}

        def conversations_for_session(self, session_id, fetch_n):
            assert session_id == 'session'
            assert fetch_n == 2
            return [('question', 'answer')]

    monkeypatch.setattr(
        opencode_provider,
        'load_session_data',
        lambda *_args, **_kwargs: (None, {'opencode_project_id': 'proj-9'}),
    )
    monkeypatch.setitem(
        sys.modules,
        'provider_backends.opencode.comm',
        SimpleNamespace(OpenCodeLogReader=FakeOpenCodeLogReader),
    )

    context = opencode_provider.extract_from_opencode(
        work_dir=tmp_path,
        source_session_files={'opencode': '.opencode-session'},
        deduper=_Deduper(),
        formatter=_Formatter(),
        max_tokens=200,
        fallback_pairs=2,
        last_n=0,
    )

    assert context.source_provider == 'opencode'
    assert context.source_session_id == 'session'
    assert context.metadata['session_path'] == str(session_path)
    assert context.conversations == [('question', 'answer')]


def test_extract_from_opencode_raises_when_no_session_identity_exists(tmp_path: Path, monkeypatch) -> None:
    class FakeOpenCodeLogReader:
        def __init__(self, *, work_dir, project_id, session_id_filter):
            self.work_dir = work_dir
            self.project_id = project_id
            self.session_id_filter = session_id_filter

        def capture_state(self):
            return {'session_id': '', 'session_path': ''}

    monkeypatch.setattr(
        opencode_provider,
        'load_session_data',
        lambda *_args, **_kwargs: (None, {}),
    )
    monkeypatch.setitem(
        sys.modules,
        'provider_backends.opencode.comm',
        SimpleNamespace(OpenCodeLogReader=FakeOpenCodeLogReader),
    )

    with pytest.raises(SessionNotFoundError, match='No OpenCode session found'):
        opencode_provider.extract_from_opencode(
            work_dir=tmp_path,
            source_session_files={'opencode': '.opencode-session'},
            deduper=_Deduper(),
            formatter=_Formatter(),
            max_tokens=200,
            fallback_pairs=2,
            last_n=0,
        )
