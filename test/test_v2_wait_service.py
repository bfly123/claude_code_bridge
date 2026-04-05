from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from cli.context import CliContextBuilder
from cli.models import ParsedWaitCommand
from cli.services.wait import wait_for_replies


def _build_context(project_root: Path) -> object:
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    command = ParsedWaitCommand(project=None, mode='any', target='msg_1')
    return CliContextBuilder().build(command, cwd=project_root, bootstrap_if_missing=False)


def test_wait_for_replies_any_polls_until_reply_arrives(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-wait-any'
    project_root.mkdir()
    context = _build_context(project_root)
    command = ParsedWaitCommand(project=None, mode='any', target='msg_1', timeout_s=1.0)

    payloads = [
        {
            'resolved_kind': 'message',
            'attempts': [
                {
                    'attempt_id': 'att_1',
                    'message_id': 'msg_1',
                    'agent_name': 'codex',
                    'retry_index': 0,
                    'updated_at': '2026-03-30T00:00:01Z',
                }
            ],
            'replies': [],
        },
        {
            'resolved_kind': 'message',
            'attempts': [
                {
                    'attempt_id': 'att_1',
                    'message_id': 'msg_1',
                    'agent_name': 'codex',
                    'retry_index': 0,
                    'updated_at': '2026-03-30T00:00:02Z',
                }
            ],
            'replies': [
                {
                    'reply_id': 'rep_1',
                    'message_id': 'msg_1',
                    'attempt_id': 'att_1',
                    'agent_name': 'codex',
                    'terminal_status': 'completed',
                    'reason': 'task_complete',
                    'finished_at': '2026-03-30T00:00:10Z',
                    'reply': 'done',
                }
            ],
        },
    ]

    class _FakeClient:
        def trace(self, target: str) -> dict:
            assert target == 'msg_1'
            return payloads.pop(0)

    monkeypatch.setattr(
        'cli.services.wait.connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=_FakeClient()),
    )
    monkeypatch.setattr('cli.services.wait.time.sleep', lambda value: None)

    summary = wait_for_replies(context, command)

    assert summary.mode == 'any'
    assert summary.target == 'msg_1'
    assert summary.resolved_kind == 'message'
    assert summary.expected_count == 1
    assert summary.received_count == 1
    assert summary.terminal_count == 1
    assert summary.notice_count == 0
    assert summary.wait_status == 'satisfied'
    assert summary.replies[0]['reply_id'] == 'rep_1'
    assert summary.replies[0]['reply'] == 'done'


def test_wait_for_replies_quorum_uses_latest_attempt_per_agent(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-wait-quorum'
    project_root.mkdir()
    context = _build_context(project_root)
    command = ParsedWaitCommand(project=None, mode='quorum', target='msg_1', quorum=1, timeout_s=1.0)

    payload = {
        'resolved_kind': 'message',
        'attempts': [
            {
                'attempt_id': 'att_old',
                'message_id': 'msg_1',
                'agent_name': 'codex',
                'retry_index': 0,
                'updated_at': '2026-03-30T00:00:02Z',
            },
            {
                'attempt_id': 'att_new',
                'message_id': 'msg_1',
                'agent_name': 'codex',
                'retry_index': 1,
                'updated_at': '2026-03-30T00:00:03Z',
            },
        ],
        'replies': [
            {
                'reply_id': 'rep_old',
                'message_id': 'msg_1',
                'attempt_id': 'att_old',
                'agent_name': 'codex',
                'terminal_status': 'incomplete',
                'reason': 'need_retry',
                'finished_at': '2026-03-30T00:00:04Z',
                'reply': 'retry me',
            },
            {
                'reply_id': 'rep_new',
                'message_id': 'msg_1',
                'attempt_id': 'att_new',
                'agent_name': 'codex',
                'terminal_status': 'completed',
                'reason': 'task_complete',
                'finished_at': '2026-03-30T00:00:05Z',
                'reply': 'final answer',
            },
        ],
    }

    class _FakeClient:
        def trace(self, target: str) -> dict:
            assert target == 'msg_1'
            return payload

    monkeypatch.setattr(
        'cli.services.wait.connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=_FakeClient()),
    )

    summary = wait_for_replies(context, command)

    assert summary.mode == 'quorum'
    assert summary.expected_count == 1
    assert summary.received_count == 1
    assert summary.terminal_count == 1
    assert summary.notice_count == 0
    assert summary.wait_status == 'satisfied'
    assert summary.replies[0]['reply_id'] == 'rep_new'
    assert summary.replies[0]['reply'] == 'final answer'


def test_wait_for_replies_returns_notice_when_heartbeat_arrives_first(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-wait-heartbeat'
    project_root.mkdir()
    context = _build_context(project_root)
    command = ParsedWaitCommand(project=None, mode='any', target='msg_1', timeout_s=1.0)

    payload = {
        'resolved_kind': 'message',
        'attempts': [
            {
                'attempt_id': 'att_1',
                'message_id': 'msg_1',
                'agent_name': 'codex',
                'job_id': 'job_1',
                'retry_index': 0,
                'updated_at': '2026-03-30T00:10:00Z',
            }
        ],
        'replies': [
            {
                'reply_id': 'rep_heartbeat',
                'message_id': 'msg_1',
                'attempt_id': 'att_1',
                'agent_name': 'codex',
                'terminal_status': 'incomplete',
                'notice': True,
                'notice_kind': 'heartbeat',
                'last_progress_at': '2026-03-30T00:00:00Z',
                'heartbeat_silence_seconds': 600.0,
                'reason': None,
                'finished_at': '2026-03-30T00:10:00Z',
                'reply': 'task still running',
            }
        ],
    }

    class _FakeClient:
        def trace(self, target: str) -> dict:
            assert target == 'msg_1'
            return payload

    monkeypatch.setattr(
        'cli.services.wait.connect_mounted_daemon',
        lambda context, allow_restart_stale: SimpleNamespace(client=_FakeClient()),
    )

    summary = wait_for_replies(context, command)

    assert summary.wait_status == 'notice'
    assert summary.received_count == 1
    assert summary.terminal_count == 0
    assert summary.notice_count == 1
    assert summary.replies[0]['notice'] is True
    assert summary.replies[0]['notice_kind'] == 'heartbeat'
    assert summary.replies[0]['job_id'] == 'job_1'
