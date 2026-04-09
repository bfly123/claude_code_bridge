from __future__ import annotations

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from ccbd.api_models import DeliveryScope
from ccbd.socket_client import CcbdClientError
from cli.context import CliContextBuilder
from cli.models import ParsedAskCommand
from cli.services import ask as ask_service
from cli.services.daemon import CcbdServiceError


def _build_context(project_root: Path) -> object:
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('cmd; agent1:codex, agent2:claude\n', encoding='utf-8')
    command = ParsedAskCommand(project=None, target='agent1', sender=None, message='hello')
    return CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)


def test_submit_ask_rejects_unknown_target(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-ask-unknown-target'
    project_root.mkdir()
    context = _build_context(project_root)

    with pytest.raises(ValueError) as exc_info:
        ask_service.submit_ask(
            context,
            ParsedAskCommand(project=None, target='agent9', sender=None, message='hello'),
        )

    assert str(exc_info.value) == 'unknown agent: agent9'


def test_submit_ask_maps_broadcast_payload_and_submission(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-ask-broadcast'
    project_root.mkdir()
    context = _build_context(project_root)
    captured: dict[str, object] = {}

    class _FakeClient:
        def submit(self, envelope) -> dict:
            captured['project_id'] = envelope.project_id
            captured['to_agent'] = envelope.to_agent
            captured['from_actor'] = envelope.from_actor
            captured['body'] = envelope.body
            captured['reply_to'] = envelope.reply_to
            captured['message_type'] = envelope.message_type
            captured['delivery_scope'] = envelope.delivery_scope
            captured['silence_on_success'] = envelope.silence_on_success
            return {
                'submission_id': 'sub_1',
                'jobs': [
                    {'job_id': 'job_1', 'agent_name': 'agent1', 'target_name': 'agent1', 'status': 'accepted'},
                    {'job_id': 'job_2', 'agent_name': 'agent2', 'target_name': 'agent2', 'status': 'accepted'},
                ],
            }

    monkeypatch.setattr(
        ask_service,
        'load_project_config',
        lambda project_root: SimpleNamespace(config=SimpleNamespace(agents={'agent1': {}, 'agent2': {}})),
    )
    monkeypatch.setattr(ask_service, 'resolve_ask_sender', lambda context, sender: 'agent1')
    monkeypatch.setattr(
        ask_service,
        'connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=_FakeClient()),
    )

    summary = ask_service.submit_ask(
        context,
        ParsedAskCommand(
            project=None,
            target='all',
            sender=None,
            message='ship it',
            reply_to='msg_1',
            mode='notify',
            silence=True,
        ),
    )

    assert summary.project_id == context.project.project_id
    assert summary.submission_id == 'sub_1'
    assert [job['job_id'] for job in summary.jobs] == ['job_1', 'job_2']
    assert captured == {
        'project_id': context.project.project_id,
        'to_agent': 'all',
        'from_actor': 'agent1',
        'body': 'ship it',
        'reply_to': 'msg_1',
        'message_type': 'notify',
        'delivery_scope': DeliveryScope.BROADCAST,
        'silence_on_success': True,
    }


def test_submit_ask_aliases_explicit_cmd_sender_to_user(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-ask-explicit-cmd'
    project_root.mkdir()
    context = _build_context(project_root)
    captured: dict[str, object] = {}

    class _FakeClient:
        def submit(self, envelope) -> dict:
            captured['from_actor'] = envelope.from_actor
            return {
                'job_id': 'job_1',
                'agent_name': 'agent1',
                'target_kind': 'agent',
                'target_name': 'agent1',
                'status': 'accepted',
            }

    monkeypatch.setattr(
        ask_service,
        'load_project_config',
        lambda project_root: SimpleNamespace(config=SimpleNamespace(agents={'agent1': {}, 'agent2': {}})),
    )
    monkeypatch.setattr(
        ask_service,
        'connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=_FakeClient()),
    )

    ask_service.submit_ask(
        context,
        ParsedAskCommand(project=None, target='agent1', sender='cmd', message='hello'),
    )

    assert captured['from_actor'] == 'user'


def test_watch_ask_job_reconnects_and_preserves_cursor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-ask-watch'
    project_root.mkdir()
    context = _build_context(project_root)
    rendered: list[tuple[str, ...]] = []

    class _FlakyClient:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def watch(self, job_id: str, *, cursor: int = 0) -> dict:
            assert job_id == 'job_1'
            self.calls.append(cursor)
            if cursor == 0:
                return {
                    'job_id': 'job_1',
                    'agent_name': 'agent1',
                    'target_name': 'agent1',
                    'cursor': 2,
                    'generation': 1,
                    'terminal': False,
                    'status': 'running',
                    'reply': 'partial',
                    'events': [
                        {'event_id': 'evt_1', 'job_id': 'job_1', 'agent_name': 'agent1', 'type': 'job_started', 'timestamp': '2026-04-06T00:00:01Z'},
                    ],
                }
            raise CcbdClientError('socket closed')

    class _StableClient:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def watch(self, job_id: str, *, cursor: int = 0) -> dict:
            assert job_id == 'job_1'
            self.calls.append(cursor)
            return {
                'job_id': 'job_1',
                'agent_name': 'agent1',
                'target_name': 'agent1',
                'cursor': 4,
                'generation': 2,
                'terminal': True,
                'status': 'completed',
                'reply': 'done',
                'events': [],
            }

    flaky = _FlakyClient()
    stable = _StableClient()
    handles = iter([SimpleNamespace(client=flaky), SimpleNamespace(client=stable)])

    monkeypatch.setattr(ask_service, 'connect_mounted_daemon', lambda context, allow_restart_stale: next(handles))
    monkeypatch.setattr(ask_service, 'ask_wait_timeout_seconds', lambda: 1.0)
    monkeypatch.setattr(ask_service, 'ask_wait_poll_interval_seconds', lambda: 0.0)
    monkeypatch.setattr(ask_service, 'render_watch_batch', lambda batch: (f'{batch.job_id}:{batch.cursor}:{batch.terminal}',))
    monkeypatch.setattr(ask_service, 'write_lines', lambda out, lines: rendered.append(lines))
    monkeypatch.setattr(ask_service.time, 'sleep', lambda seconds: None)

    batch = ask_service.watch_ask_job(context, 'job_1', StringIO(), timeout=None, emit_output=True)

    assert batch.cursor == 4
    assert batch.generation == 2
    assert batch.reply == 'done'
    assert flaky.calls == [0, 2]
    assert stable.calls == [2]
    assert rendered == [('job_1:2:False',), ('job_1:4:True',)]


def test_watch_ask_job_times_out_after_reconnect_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-ask-timeout'
    project_root.mkdir()
    context = _build_context(project_root)
    clock = iter([0.0, 0.5, 1.5])

    class _FlakyClient:
        def watch(self, job_id: str, *, cursor: int = 0) -> dict:
            del job_id, cursor
            raise CcbdClientError('socket closed')

    monkeypatch.setattr(
        ask_service,
        'connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=_FlakyClient()),
    )
    monkeypatch.setattr(ask_service, 'ask_wait_timeout_seconds', lambda: 1.0)
    monkeypatch.setattr(ask_service, 'ask_wait_poll_interval_seconds', lambda: 0.0)
    monkeypatch.setattr(ask_service.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(ask_service.time, 'sleep', lambda seconds: None)

    with pytest.raises(RuntimeError) as exc_info:
        ask_service.watch_ask_job(context, 'job_1', StringIO(), timeout=None, emit_output=False)

    assert str(exc_info.value) == 'wait timed out for job_1'


def test_watch_ask_job_retries_when_reconnect_attempt_temporarily_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / 'repo-ask-reconnect-step-fail'
    project_root.mkdir()
    context = _build_context(project_root)
    clock = iter([0.0, 0.1, 0.2, 0.3, 0.4, 0.5])

    class _FlakyClient:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def watch(self, job_id: str, *, cursor: int = 0) -> dict:
            assert job_id == 'job_1'
            self.calls.append(cursor)
            raise CcbdClientError('socket closed')

    class _StableClient:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def watch(self, job_id: str, *, cursor: int = 0) -> dict:
            assert job_id == 'job_1'
            self.calls.append(cursor)
            return {
                'job_id': 'job_1',
                'agent_name': 'agent1',
                'target_name': 'agent1',
                'cursor': 1,
                'generation': 2,
                'terminal': True,
                'status': 'completed',
                'reply': 'done',
                'events': [],
            }

    flaky = _FlakyClient()
    stable = _StableClient()
    connects = {'count': 0}

    def _connect(context, allow_restart_stale):
        del context, allow_restart_stale
        connects['count'] += 1
        if connects['count'] == 1:
            return SimpleNamespace(client=flaky)
        if connects['count'] == 2:
            raise CcbdServiceError('daemon restarting')
        return SimpleNamespace(client=stable)

    monkeypatch.setattr(ask_service, 'connect_mounted_daemon', _connect)
    monkeypatch.setattr(ask_service, 'ask_wait_timeout_seconds', lambda: 1.0)
    monkeypatch.setattr(ask_service, 'ask_wait_poll_interval_seconds', lambda: 0.0)
    monkeypatch.setattr(ask_service.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(ask_service.time, 'sleep', lambda seconds: None)

    batch = ask_service.watch_ask_job(context, 'job_1', StringIO(), timeout=None, emit_output=False)

    assert batch.terminal is True
    assert batch.reply == 'done'
    assert flaky.calls == [0]
    assert stable.calls == [0]


def test_write_ask_output_appends_newline(tmp_path: Path) -> None:
    path = tmp_path / 'reply.txt'

    ask_service.write_ask_output(path, 'done')

    assert path.read_text(encoding='utf-8') == 'done\n'


def test_exit_code_for_ask_status_prefers_no_reply_exit_for_incomplete_with_reply() -> None:
    assert ask_service.exit_code_for_ask_status('incomplete', reply='partial') == 2
    assert ask_service.exit_code_for_ask_status('completed', reply='done') == 0
    assert ask_service.exit_code_for_ask_status('failed', reply='') == 1
