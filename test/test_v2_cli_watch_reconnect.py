from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ccbd.socket_client import CcbdClientError
from cli.context import CliContext, CliContextBuilder
from cli.models import ParsedPendCommand, ParsedWatchCommand
from cli.services import pend as pend_service
from cli.services import watch as watch_service
from storage.paths import PathLayout


class _FlakyWatchClient:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def watch(self, target: str, *, cursor: int = 0) -> dict:
        del target
        self.calls.append(cursor)
        raise CcbdClientError('socket closed during generation switch')


class _StableWatchClient:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def watch(self, target: str, *, cursor: int = 0) -> dict:
        del target
        self.calls.append(cursor)
        return {
            'job_id': 'job_demo',
            'agent_name': 'codex',
            'cursor': cursor,
            'generation': 2,
            'terminal': True,
            'status': 'completed',
            'reply': 'done',
            'events': [],
        }


class _StreamingWatchClient:
    def __init__(self, *responses: dict) -> None:
        self._responses = list(responses)
        self.calls: list[int] = []

    def watch(self, target: str, *, cursor: int = 0) -> dict:
        del target
        self.calls.append(cursor)
        if not self._responses:
            raise AssertionError('no more watch responses configured')
        return dict(self._responses.pop(0))


class _StreamingThenFlakyWatchClient:
    def __init__(self, response: dict) -> None:
        self._response = dict(response)
        self._used = False
        self.calls: list[int] = []

    def watch(self, target: str, *, cursor: int = 0) -> dict:
        del target
        self.calls.append(cursor)
        if not self._used:
            self._used = True
            return dict(self._response)
        raise CcbdClientError('socket closed during generation switch')


class _FlakyPendClient:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, job_id: str) -> dict:
        del job_id
        self.calls += 1
        raise CcbdClientError('stale socket')


class _StablePendClient:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, job_id: str) -> dict:
        del job_id
        self.calls += 1
        return {
            'job_id': 'job_demo',
            'agent_name': 'codex',
            'status': 'completed',
            'reply': 'done',
            'completion_reason': 'task_complete',
            'completion_confidence': 'exact',
            'updated_at': '2026-03-18T00:00:10Z',
            'generation': 2,
        }


class _MailboxPendClient:
    def request(self, op: str, payload: dict) -> dict:
        assert op == 'get'
        assert payload == {'agent_name': 'claude'}
        return {
            'job_id': 'job_demo',
            'agent_name': 'claude',
            'status': 'running',
            'reply': '',
            'completion_reason': None,
            'completion_confidence': None,
            'updated_at': '2026-03-18T00:00:05Z',
            'generation': 2,
        }

    def inbox(self, agent_name: str) -> dict:
        assert agent_name == 'claude'
        return {
            'head': {
                'reply_id': 'rep_1',
                'source_actor': 'codex',
                'reply_terminal_status': 'incomplete',
                'reply_notice': True,
                'reply_notice_kind': 'heartbeat',
                'reply_finished_at': '2026-03-18T00:10:00Z',
                'reply_last_progress_at': '2026-03-18T00:00:00Z',
                'reply_heartbeat_silence_seconds': 600.0,
                'job_id': 'job_demo',
                'reply': 'task still running',
            }
        }


def _context(project_root: Path) -> CliContext:
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    command = ParsedWatchCommand(project=None, target='job_demo')
    return CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)


def test_watch_target_reconnects_after_socket_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    context = _context(project_root)
    flaky = _FlakyWatchClient()
    stable = _StableWatchClient()
    handles = iter(
        [
            SimpleNamespace(client=flaky),
            SimpleNamespace(client=stable),
        ]
    )

    monkeypatch.setattr(watch_service, 'connect_mounted_daemon', lambda context, allow_restart_stale: next(handles))
    monkeypatch.setenv('CCB_WATCH_TIMEOUT_S', '1')
    monkeypatch.setenv('CCB_WATCH_POLL_INTERVAL_S', '0')

    batches = list(watch_service.watch_target(context, ParsedWatchCommand(project=None, target='job_demo')))
    assert len(batches) == 1
    assert batches[0].terminal is True
    assert batches[0].generation == 2
    assert flaky.calls == [0]
    assert stable.calls == [0]


def test_watch_target_preserves_cursor_across_reconnect(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-cursor'
    project_root.mkdir()
    context = _context(project_root)
    first = _StreamingThenFlakyWatchClient(
        {
            'job_id': 'job_demo',
            'agent_name': 'codex',
            'cursor': 2,
            'generation': 1,
            'terminal': False,
            'status': 'running',
            'reply': 'partial',
            'events': [
                {'event_id': 'evt1', 'job_id': 'job_demo', 'agent_name': 'codex', 'type': 'job_started', 'timestamp': '2026-03-18T00:00:01Z'},
            ],
        }
    )
    second = _StreamingWatchClient(
        {
            'job_id': 'job_demo',
            'agent_name': 'codex',
            'cursor': 4,
            'generation': 2,
            'terminal': True,
            'status': 'completed',
            'reply': 'final',
            'events': [
                {'event_id': 'evt2', 'job_id': 'job_demo', 'agent_name': 'codex', 'type': 'completion_terminal', 'timestamp': '2026-03-18T00:00:02Z'},
                {'event_id': 'evt3', 'job_id': 'job_demo', 'agent_name': 'codex', 'type': 'job_completed', 'timestamp': '2026-03-18T00:00:02Z'},
            ],
        }
    )
    handles = iter(
        [
            SimpleNamespace(client=first),
            SimpleNamespace(client=second),
        ]
    )

    monkeypatch.setattr(watch_service, 'connect_mounted_daemon', lambda context, allow_restart_stale: next(handles))
    monkeypatch.setenv('CCB_WATCH_TIMEOUT_S', '1')
    monkeypatch.setenv('CCB_WATCH_POLL_INTERVAL_S', '0')

    batches = list(watch_service.watch_target(context, ParsedWatchCommand(project=None, target='job_demo')))
    assert len(batches) == 2
    assert [batch.cursor for batch in batches] == [2, 4]
    assert [batch.generation for batch in batches] == [1, 2]
    assert [batch.terminal for batch in batches] == [False, True]
    assert first.calls == [0, 2]
    assert second.calls == [2]


def test_pend_target_reconnects_after_socket_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    context = _context(project_root)
    flaky = _FlakyPendClient()
    stable = _StablePendClient()
    handles = iter(
        [
            SimpleNamespace(client=flaky),
            SimpleNamespace(client=stable),
        ]
    )

    monkeypatch.setattr(pend_service, 'connect_mounted_daemon', lambda context, allow_restart_stale: next(handles))

    payload = pend_service.pend_target(context, ParsedPendCommand(project=None, target='job_demo'))
    assert payload['status'] == 'completed'
    assert payload['generation'] == 2
    assert flaky.calls == 1
    assert stable.calls == 1


def test_pend_target_merges_mailbox_head_reply_for_agent_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-pend-mailbox'
    project_root.mkdir()
    context = _context(project_root)

    monkeypatch.setattr(
        pend_service,
        'connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=_MailboxPendClient()),
    )

    payload = pend_service.pend_target(context, ParsedPendCommand(project=None, target='claude'))

    assert payload['status'] == 'running'
    assert payload['mailbox_reply_ready'] is True
    assert payload['mailbox_reply_id'] == 'rep_1'
    assert payload['mailbox_reply_notice'] is True
    assert payload['mailbox_reply_notice_kind'] == 'heartbeat'
    assert payload['mailbox_reply_job_id'] == 'job_demo'
