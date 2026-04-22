from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from ccbd.services.dispatcher_runtime.reply_delivery_runtime import cmd_body_store
from ccbd.services.dispatcher_runtime.reply_delivery_runtime.cmd_transport_planner import (
    _BODY_CHAR_THRESHOLD,
    CmdDeliveryFallback,
    CmdDeliveryPlan,
    header_only_enabled,
    plan_cmd_delivery,
)


def _make_reply(*, body: str = 'done', reply_id: str = 'rep-1', heartbeat: bool = False):
    diagnostics: dict = {}
    if heartbeat:
        diagnostics['notice_kind'] = 'heartbeat'
    return SimpleNamespace(
        attempt_id='att-1',
        agent_name='agent2',
        reply_id=reply_id,
        terminal_status=SimpleNamespace(value='succeeded'),
        diagnostics=diagnostics,
        reply=body,
    )


def _make_dispatcher(*, job_id: str = 'job-1', task_id: str = 'task-9'):
    source_job = SimpleNamespace(job_id=job_id, request=SimpleNamespace(task_id=task_id))
    return SimpleNamespace(
        _message_bureau_control=SimpleNamespace(
            _attempt_store=SimpleNamespace(get_latest=lambda attempt_id: SimpleNamespace(job_id=job_id))
        ),
        get_job=lambda jid: source_job,
    )


@pytest.fixture
def _no_env_override(monkeypatch):
    monkeypatch.delenv('CCB_HEADER_ONLY', raising=False)


def test_short_body_returns_full_plan(tmp_path: Path, _no_env_override) -> None:
    reply = _make_reply(body='short')
    plan, fallback = plan_cmd_delivery(_make_dispatcher(), reply, project_root=tmp_path, body_store=cmd_body_store)
    assert isinstance(plan, CmdDeliveryPlan)
    assert plan.header_only is False
    assert plan.body_file is None
    assert 'short' in plan.body
    assert fallback is None


def test_long_body_switches_to_header_only(tmp_path: Path, _no_env_override) -> None:
    long_body = 'x' * (_BODY_CHAR_THRESHOLD + 1)
    reply = _make_reply(body=long_body, reply_id='rep-long-1')
    plan, fallback = plan_cmd_delivery(_make_dispatcher(), reply, project_root=tmp_path, body_store=cmd_body_store)
    assert plan.header_only is True
    assert plan.body_file is not None
    assert plan.body_file.exists()
    assert plan.body_file.read_text(encoding='utf-8') == long_body
    # Injected body is the header-only variant, not the full body.
    assert 'must_read=1' in plan.body
    assert 'body_file=' in plan.body
    assert long_body not in plan.body
    assert fallback is None


def test_header_only_body_includes_structured_notice_line(tmp_path: Path, _no_env_override) -> None:
    # Codex review 2026-04-22: NOTICE must be a machine-parseable key=value
    # line on its own so it cannot be skimmed past like prose.
    long_body = 'n' * (_BODY_CHAR_THRESHOLD + 1)
    reply = _make_reply(body=long_body, reply_id='rep-notice-1')
    plan, _ = plan_cmd_delivery(_make_dispatcher(), reply, project_root=tmp_path, body_store=cmd_body_store)
    lines = plan.body.splitlines()
    # Line 0 is CCB_REPLY header; line 1 must be the structured NOTICE.
    assert lines[0].startswith('CCB_REPLY ')
    assert lines[1].startswith('CCB_NOTICE ')
    assert 'kind=external_body' in lines[1]
    assert 'must_read=1' in lines[1]
    assert 'body_file=' in lines[1]
    # Human-readable orientation follows; must_read appears twice overall
    # (header + notice) so the hard signal cannot be missed.
    assert plan.body.count('must_read=1') >= 2
    assert 'Read tool' in plan.body


def test_long_body_without_project_root_falls_back_to_full(tmp_path: Path, _no_env_override) -> None:
    long_body = 'y' * (_BODY_CHAR_THRESHOLD + 1)
    reply = _make_reply(body=long_body, reply_id='rep-long-2')
    plan, fallback = plan_cmd_delivery(_make_dispatcher(), reply, project_root=None, body_store=cmd_body_store)
    assert plan.header_only is False
    assert plan.body_file is None
    # Falls back to full body so delivery never blocks solely on missing layout.
    assert long_body in plan.body
    # Codex review 2026-04-22: the fallback reason must be observable so the
    # rollout observation window cannot silently lie about adoption rate.
    assert fallback is not None
    assert fallback.reason == 'project_root_unavailable'
    assert fallback.body_char_count == len(long_body)


def test_heartbeat_always_full_even_when_long(tmp_path: Path, _no_env_override) -> None:
    long_body = 'z' * (_BODY_CHAR_THRESHOLD + 1)
    reply = _make_reply(body=long_body, reply_id='rep-hb-1', heartbeat=True)
    plan, fallback = plan_cmd_delivery(_make_dispatcher(), reply, project_root=tmp_path, body_store=cmd_body_store)
    # Heartbeat notices carry job-status signal that must arrive intact.
    assert plan.header_only is False
    assert plan.body_file is None
    assert fallback is None


def test_body_file_path_quoted_when_contains_spaces(tmp_path: Path, _no_env_override) -> None:
    project_root = tmp_path / 'dir with spaces'
    long_body = 'q' * (_BODY_CHAR_THRESHOLD + 1)
    reply = _make_reply(body=long_body, reply_id='rep-space-1')
    plan, _ = plan_cmd_delivery(_make_dispatcher(), reply, project_root=project_root, body_store=cmd_body_store)
    assert plan.header_only is True
    header_line = plan.body.splitlines()[0]
    # shlex.quote wraps the value in single quotes when it contains spaces so
    # the CCB_REPLY token boundary survives.
    assert "body_file='" in header_line
    assert "must_read=1" in header_line


def test_threshold_boundary_inclusive_short(tmp_path: Path, _no_env_override) -> None:
    reply = _make_reply(body='a' * _BODY_CHAR_THRESHOLD)
    plan, fallback = plan_cmd_delivery(_make_dispatcher(), reply, project_root=tmp_path, body_store=cmd_body_store)
    # Exactly threshold is still the short path.
    assert plan.header_only is False
    assert plan.body_file is None
    assert fallback is None


def test_summary_extracts_three_nonempty_lines(tmp_path: Path, _no_env_override) -> None:
    long_body = '\n'.join([
        'line-1 first',
        '',
        'line-2 second',
        '',
        'line-3 third',
        'line-4 never-seen',
    ]) + ('x' * (_BODY_CHAR_THRESHOLD + 1))
    reply = _make_reply(body=long_body, reply_id='rep-summary-1')
    plan, _ = plan_cmd_delivery(_make_dispatcher(), reply, project_root=tmp_path, body_store=cmd_body_store)
    assert plan.header_only is True
    assert 'line-1 first' in plan.body
    assert 'line-2 second' in plan.body
    assert 'line-3 third' in plan.body
    assert 'line-4 never-seen' not in plan.body


def test_source_job_fields_included_in_header(tmp_path: Path, _no_env_override) -> None:
    long_body = 'u' * (_BODY_CHAR_THRESHOLD + 1)
    reply = _make_reply(body=long_body, reply_id='rep-job-1')
    plan, _ = plan_cmd_delivery(
        _make_dispatcher(job_id='job-xyz', task_id='task-abc'),
        reply,
        project_root=tmp_path,
        body_store=cmd_body_store,
    )
    header_line = plan.body.splitlines()[0]
    assert 'from=agent2' in header_line
    assert 'reply=rep-job-1' in header_line
    assert 'status=succeeded' in header_line
    assert 'job=job-xyz' in header_line
    assert 'task=task-abc' in header_line


# --- Kill switch ---

def test_header_only_enabled_default_is_true(_no_env_override) -> None:
    assert header_only_enabled() is True


@pytest.mark.parametrize('value', ['0', 'false', 'no', 'off', ''])
def test_header_only_enabled_falsy_env_disables(monkeypatch, value: str) -> None:
    monkeypatch.setenv('CCB_HEADER_ONLY', value)
    assert header_only_enabled() is False


@pytest.mark.parametrize('value', ['1', 'true', 'yes', 'on', 'anything-else'])
def test_header_only_enabled_truthy_env_enables(monkeypatch, value: str) -> None:
    monkeypatch.setenv('CCB_HEADER_ONLY', value)
    assert header_only_enabled() is True


def test_kill_switch_forces_full_body_even_for_long_reply(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('CCB_HEADER_ONLY', '0')
    long_body = 'k' * (_BODY_CHAR_THRESHOLD + 1)
    reply = _make_reply(body=long_body, reply_id='rep-kill-1')
    plan, fallback = plan_cmd_delivery(_make_dispatcher(), reply, project_root=tmp_path, body_store=cmd_body_store)
    assert plan.header_only is False
    assert plan.body_file is None
    assert long_body in plan.body
    assert fallback is not None
    assert fallback.reason == 'kill_switch_disabled'
    assert fallback.body_char_count == len(long_body)


def test_fallback_dataclass_is_frozen() -> None:
    fb = CmdDeliveryFallback(reason='kill_switch_disabled', body_char_count=42)
    with pytest.raises(AttributeError):
        fb.reason = 'other'  # type: ignore[misc]
