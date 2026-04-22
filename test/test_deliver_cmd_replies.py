"""Direct tests for _deliver_cmd_replies side-effect-only delivery.

The function's contract:
- It NEVER claims/consumes/abandons the head except for malformed payloads
  (true permanent failure). Human ack via client.ack('cmd') is the consumer.
- Idempotent: a reply already injected in this dispatcher's lifetime is not
  re-injected on subsequent ticks until the user acks.
- Environmental failures (no pane, dead backend, send error) leave the head
  QUEUED so the next tick retries.
- Plan/send exceptions emit cmd_phase2_failure telemetry but don't burn the
  head.

These tests use SimpleNamespace fakes for dispatcher/kernel/control rather
than full integration scaffolding so the failure modes can be exercised
deterministically.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mailbox_kernel import InboundEventStatus, InboundEventType
from ccbd.services.dispatcher_runtime.reply_delivery_runtime import (
    preparation_service,
)


class _RecordingKernel:
    def __init__(self, head):
        self._head = head
        self.calls: list[tuple[str, str]] = []  # (method, inbound_event_id)

    def head_pending_event(self, agent_name: str):
        return self._head

    def claim(self, agent_name: str, inbound_event_id: str, *, started_at=None):
        self.calls.append(('claim', inbound_event_id))
        return self._head

    def consume(self, agent_name: str, inbound_event_id: str, *, finished_at=None):
        self.calls.append(('consume', inbound_event_id))
        return self._head

    def abandon(self, agent_name: str, inbound_event_id: str, *, finished_at=None):
        self.calls.append(('abandon', inbound_event_id))
        return self._head


class _RecordingBackend:
    def __init__(self, *, alive: bool = True, send_raises: bool = False):
        self._alive = alive
        self._send_raises = send_raises
        self.injected: list[tuple[str, str]] = []

    def is_alive(self, pane_id: str) -> bool:
        return self._alive

    def send_text_to_pane(self, pane_id: str, text: str):
        if self._send_raises:
            raise RuntimeError('inject failed')
        self.injected.append((pane_id, text))


def _make_head(*, status=InboundEventStatus.QUEUED, payload_ref='reply:rep-1'):
    return SimpleNamespace(
        inbound_event_id='evt-1',
        event_type=InboundEventType.TASK_REPLY,
        status=status,
        payload_ref=payload_ref,
    )


def _make_reply(*, reply_id='rep-1', body='hello cmd'):
    return SimpleNamespace(
        attempt_id='att-1',
        agent_name='codex',
        reply_id=reply_id,
        terminal_status=SimpleNamespace(value='succeeded'),
        diagnostics={},
        reply=body,
    )


def _make_dispatcher(
    *,
    head,
    reply,
    backend,
    pane_id='%1',
    project_root=None,
    job_id='job-1',
    task_id='task-1',
):
    """Wire up a dispatcher SimpleNamespace with the minimum surface area
    that _deliver_cmd_replies and its helpers reach for."""
    kernel = _RecordingKernel(head)
    reply_store = SimpleNamespace(get_latest=lambda rid: reply if reply and reply.reply_id == rid else None)
    attempt_store = SimpleNamespace(get_latest=lambda aid: SimpleNamespace(job_id=job_id))
    control = SimpleNamespace(
        _mailbox_kernel=kernel,
        _reply_store=reply_store,
        _attempt_store=attempt_store,
    )
    layout = SimpleNamespace(project_root=project_root) if project_root is not None else None

    dispatcher = SimpleNamespace(
        _message_bureau_control=control,
        _layout=layout,
        _clock=lambda: '2026-04-23T00:00:00+00:00',
        get_job=lambda jid: SimpleNamespace(job_id=job_id, request=SimpleNamespace(task_id=task_id)),
    )
    # Attach helpers to the dispatcher so the production code's
    # _discover_cmd_pane_id / _get_tmux_backend can be monkeypatched in
    # individual tests.
    return dispatcher, kernel


@pytest.fixture
def _stub_pane_and_backend(monkeypatch):
    """By default, return a working pane + backend. Tests override per-need."""
    backend = _RecordingBackend()
    monkeypatch.setattr(preparation_service, '_discover_cmd_pane_id', lambda d: '%1')
    monkeypatch.setattr(preparation_service, '_get_tmux_backend', lambda d: backend)
    return backend


# --- Happy path ---

def test_inject_sends_text_and_does_not_claim_or_consume(
    _stub_pane_and_backend, monkeypatch
):
    head = _make_head()
    reply = _make_reply(body='short reply text')
    dispatcher, kernel = _make_dispatcher(head=head, reply=reply, backend=_stub_pane_and_backend)

    preparation_service._deliver_cmd_replies(dispatcher)

    # The head was NOT touched.
    assert kernel.calls == [], f'expected no kernel state mutations, got {kernel.calls}'
    # The pane received the text.
    assert len(_stub_pane_and_backend.injected) == 1
    pane_id, text = _stub_pane_and_backend.injected[0]
    assert pane_id == '%1'
    assert 'short reply text' in text


def test_idempotent_no_reinject_on_second_call(_stub_pane_and_backend):
    head = _make_head()
    reply = _make_reply(body='one-shot text')
    dispatcher, kernel = _make_dispatcher(head=head, reply=reply, backend=_stub_pane_and_backend)

    preparation_service._deliver_cmd_replies(dispatcher)
    preparation_service._deliver_cmd_replies(dispatcher)
    preparation_service._deliver_cmd_replies(dispatcher)

    assert len(_stub_pane_and_backend.injected) == 1, 'should inject exactly once for the same reply_id'
    assert kernel.calls == []


# --- Permanent failure: malformed payload ---

def test_malformed_payload_abandons_head(_stub_pane_and_backend):
    # No 'reply:' prefix → reply_id_from_payload returns ''
    head = _make_head(payload_ref='not-a-reply-ref')
    reply = _make_reply()
    dispatcher, kernel = _make_dispatcher(head=head, reply=reply, backend=_stub_pane_and_backend)

    preparation_service._deliver_cmd_replies(dispatcher)

    assert kernel.calls == [('abandon', 'evt-1')], (
        f'malformed payload must be abandoned (true permanent failure), got {kernel.calls}'
    )
    assert _stub_pane_and_backend.injected == []


# --- Environmental failures: head must stay queued ---

def test_no_pane_silent_return_head_untouched(monkeypatch):
    head = _make_head()
    reply = _make_reply()
    backend = _RecordingBackend()
    monkeypatch.setattr(preparation_service, '_discover_cmd_pane_id', lambda d: None)
    monkeypatch.setattr(preparation_service, '_get_tmux_backend', lambda d: backend)
    dispatcher, kernel = _make_dispatcher(head=head, reply=reply, backend=backend)

    preparation_service._deliver_cmd_replies(dispatcher)

    assert kernel.calls == [], 'no pane → silent return, head must NOT be claimed/abandoned'
    assert backend.injected == []


def test_no_backend_silent_return_head_untouched(monkeypatch):
    head = _make_head()
    reply = _make_reply()
    monkeypatch.setattr(preparation_service, '_discover_cmd_pane_id', lambda d: '%1')
    monkeypatch.setattr(preparation_service, '_get_tmux_backend', lambda d: None)
    dispatcher, kernel = _make_dispatcher(head=head, reply=reply, backend=None)

    preparation_service._deliver_cmd_replies(dispatcher)

    assert kernel.calls == [], 'no backend → silent return'


def test_pane_not_alive_silent_return_head_untouched(monkeypatch):
    head = _make_head()
    reply = _make_reply()
    backend = _RecordingBackend(alive=False)
    monkeypatch.setattr(preparation_service, '_discover_cmd_pane_id', lambda d: '%1')
    monkeypatch.setattr(preparation_service, '_get_tmux_backend', lambda d: backend)
    dispatcher, kernel = _make_dispatcher(head=head, reply=reply, backend=backend)

    preparation_service._deliver_cmd_replies(dispatcher)

    assert kernel.calls == []
    assert backend.injected == []


def test_send_failure_does_not_claim_or_burn_head(monkeypatch):
    head = _make_head()
    reply = _make_reply()
    backend = _RecordingBackend(send_raises=True)
    monkeypatch.setattr(preparation_service, '_discover_cmd_pane_id', lambda d: '%1')
    monkeypatch.setattr(preparation_service, '_get_tmux_backend', lambda d: backend)
    dispatcher, kernel = _make_dispatcher(head=head, reply=reply, backend=backend)

    preparation_service._deliver_cmd_replies(dispatcher)

    # Head untouched — next tick retries when tmux recovers.
    assert kernel.calls == []
    # Cache must NOT contain the reply_id (we want retry).
    cache = preparation_service._get_injected_cache(dispatcher)
    assert reply.reply_id not in cache


def test_retry_succeeds_after_transient_send_failure(monkeypatch):
    """First tick: backend rejects send. Second tick: backend healthy. Reply
    delivered exactly once and head still untouched."""
    head = _make_head()
    reply = _make_reply()
    backend = _RecordingBackend(send_raises=True)
    monkeypatch.setattr(preparation_service, '_discover_cmd_pane_id', lambda d: '%1')
    monkeypatch.setattr(preparation_service, '_get_tmux_backend', lambda d: backend)
    dispatcher, kernel = _make_dispatcher(head=head, reply=reply, backend=backend)

    preparation_service._deliver_cmd_replies(dispatcher)
    assert backend.injected == []

    backend._send_raises = False
    preparation_service._deliver_cmd_replies(dispatcher)
    assert len(backend.injected) == 1
    assert kernel.calls == []


# --- DELIVERING / unexpected status filtering ---

def test_delivering_head_is_not_re_injected(_stub_pane_and_backend):
    head = _make_head(status=InboundEventStatus.DELIVERING)
    reply = _make_reply()
    dispatcher, kernel = _make_dispatcher(head=head, reply=reply, backend=_stub_pane_and_backend)

    preparation_service._deliver_cmd_replies(dispatcher)

    assert kernel.calls == []
    assert _stub_pane_and_backend.injected == []


def test_non_task_reply_event_ignored(_stub_pane_and_backend):
    head = _make_head()
    head.event_type = InboundEventType.TASK_REQUEST  # not a reply
    reply = _make_reply()
    dispatcher, kernel = _make_dispatcher(head=head, reply=reply, backend=_stub_pane_and_backend)

    preparation_service._deliver_cmd_replies(dispatcher)

    assert kernel.calls == []
    assert _stub_pane_and_backend.injected == []


# --- Telemetry ---

def test_phase2_failure_telemetry_on_send_exception(monkeypatch, tmp_path):
    head = _make_head()
    reply = _make_reply(body='x' * 10)
    backend = _RecordingBackend(send_raises=True)
    monkeypatch.setattr(preparation_service, '_discover_cmd_pane_id', lambda d: '%1')
    monkeypatch.setattr(preparation_service, '_get_tmux_backend', lambda d: backend)
    dispatcher, kernel = _make_dispatcher(head=head, reply=reply, backend=backend, project_root=tmp_path)

    preparation_service._deliver_cmd_replies(dispatcher)

    metrics_file = tmp_path / '.ccb' / 'metrics' / 'body_read_followup.jsonl'
    assert metrics_file.exists(), 'phase2 telemetry must be written'
    records = [json.loads(line) for line in metrics_file.read_text(encoding='utf-8').splitlines() if line.strip()]
    failure_records = [r for r in records if r.get('event') == 'cmd_phase2_failure']
    assert len(failure_records) == 1
    assert failure_records[0]['stage'] == 'send'
    assert failure_records[0]['reason'] == 'exception'
    assert failure_records[0]['reply_id'] == reply.reply_id


def test_long_body_happy_path_emits_header_only_dispatch_telemetry(
    _stub_pane_and_backend, tmp_path
):
    """Long body + project_root present: pane gets the structured header-only
    payload, body is persisted to disk, and a header_only_dispatch event lands
    in the metrics log. Covers the P2 gap codex 2nd-review flagged."""
    from ccbd.services.dispatcher_runtime.reply_delivery_runtime.cmd_transport_planner import (
        _BODY_CHAR_THRESHOLD,
    )
    head = _make_head()
    long_body = 'w' * (_BODY_CHAR_THRESHOLD + 1)
    reply = _make_reply(body=long_body)
    dispatcher, kernel = _make_dispatcher(
        head=head, reply=reply, backend=_stub_pane_and_backend, project_root=tmp_path,
    )

    preparation_service._deliver_cmd_replies(dispatcher)

    # Pane got the structured header-only payload, NOT the full body.
    assert len(_stub_pane_and_backend.injected) == 1
    _, pane_text = _stub_pane_and_backend.injected[0]
    lines = pane_text.splitlines()
    assert lines[0].startswith('CCB_REPLY ')
    assert lines[1].startswith('CCB_NOTICE kind=external_body must_read=1 body_file=')
    assert long_body not in pane_text, 'long body must NOT be inlined into pane text'

    # Body file exists on disk with the full content.
    body_file = tmp_path / '.ccb' / 'replies' / 'cmd' / f'{reply.reply_id}.md'
    assert body_file.exists()
    assert body_file.read_text(encoding='utf-8') == long_body

    # header_only_dispatch event recorded.
    metrics_file = tmp_path / '.ccb' / 'metrics' / 'body_read_followup.jsonl'
    assert metrics_file.exists()
    records = [json.loads(line) for line in metrics_file.read_text(encoding='utf-8').splitlines() if line.strip()]
    dispatch_events = [r for r in records if r.get('event') == 'header_only_dispatch']
    assert len(dispatch_events) == 1
    assert dispatch_events[0]['reply_id'] == reply.reply_id
    assert dispatch_events[0]['body_file'] == str(body_file)
    assert dispatch_events[0]['body_char_count'] == len(long_body)
    assert kernel.calls == [], 'head must not be claimed/consumed in the happy path'


def test_long_body_without_project_root_records_fallback_telemetry(monkeypatch, tmp_path):
    """When project_root is None we cannot persist the body, so the planner
    degrades to full-body inject AND emits a long_reply_fell_back_full_body
    event so the observation window sees it. But with project_root None the
    event is dropped (nowhere to write) — verify full-body inject still
    happens. When project_root is PRESENT but the kill switch is off, the
    telemetry event lands."""
    from ccbd.services.dispatcher_runtime.reply_delivery_runtime.cmd_transport_planner import (
        _BODY_CHAR_THRESHOLD,
    )
    monkeypatch.setenv('CCB_HEADER_ONLY', '0')
    head = _make_head()
    long_body = 'f' * (_BODY_CHAR_THRESHOLD + 1)
    reply = _make_reply(body=long_body)
    backend = _RecordingBackend()
    monkeypatch.setattr(preparation_service, '_discover_cmd_pane_id', lambda d: '%1')
    monkeypatch.setattr(preparation_service, '_get_tmux_backend', lambda d: backend)
    dispatcher, kernel = _make_dispatcher(
        head=head, reply=reply, backend=backend, project_root=tmp_path,
    )

    preparation_service._deliver_cmd_replies(dispatcher)

    # Full body reached the pane (kill switch forced).
    assert len(backend.injected) == 1
    _, pane_text = backend.injected[0]
    assert long_body in pane_text

    # Fallback telemetry event recorded with kill_switch_disabled reason.
    metrics_file = tmp_path / '.ccb' / 'metrics' / 'body_read_followup.jsonl'
    assert metrics_file.exists()
    records = [json.loads(line) for line in metrics_file.read_text(encoding='utf-8').splitlines() if line.strip()]
    fallback_events = [r for r in records if r.get('event') == 'long_reply_fell_back_full_body']
    assert len(fallback_events) == 1
    assert fallback_events[0]['reason'] == 'kill_switch_disabled'
    assert fallback_events[0]['body_char_count'] == len(long_body)
    assert kernel.calls == []


def test_plan_exception_records_phase2_failure_telemetry(monkeypatch, tmp_path):
    """If plan_cmd_delivery itself raises (e.g., body_store write failed on
    disk-full), the planner telemetry event should fire so the failure is
    visible, and the head must NOT be burned."""
    from ccbd.services.dispatcher_runtime.reply_delivery_runtime import preparation_service as ps
    head = _make_head()
    reply = _make_reply(body='y' * 10)
    backend = _RecordingBackend()
    monkeypatch.setattr(ps, '_discover_cmd_pane_id', lambda d: '%1')
    monkeypatch.setattr(ps, '_get_tmux_backend', lambda d: backend)

    def _boom(dispatcher, reply, *, project_root, body_store):
        raise RuntimeError('disk full')
    monkeypatch.setattr(ps, 'plan_cmd_delivery', _boom)

    dispatcher, kernel = _make_dispatcher(
        head=head, reply=reply, backend=backend, project_root=tmp_path,
    )

    ps._deliver_cmd_replies(dispatcher)

    # No inject, head untouched.
    assert backend.injected == []
    assert kernel.calls == []

    # Phase2 plan failure event recorded.
    metrics_file = tmp_path / '.ccb' / 'metrics' / 'body_read_followup.jsonl'
    assert metrics_file.exists()
    records = [json.loads(line) for line in metrics_file.read_text(encoding='utf-8').splitlines() if line.strip()]
    plan_failures = [
        r for r in records
        if r.get('event') == 'cmd_phase2_failure' and r.get('stage') == 'plan'
    ]
    assert len(plan_failures) == 1
    assert plan_failures[0]['reason'] == 'exception'
    assert plan_failures[0]['reply_id'] == reply.reply_id

    # Not cached — next tick retries.
    cache = ps._get_injected_cache(dispatcher)
    assert reply.reply_id not in cache


def test_lru_cache_eviction_allows_reinject(_stub_pane_and_backend):
    """If a reply_id ages out of the bounded cache (256 entries), it can be
    re-injected. This is the documented at-least-once tradeoff — we want to
    confirm it's reachable, not prevent it."""
    head = _make_head()
    reply = _make_reply()
    dispatcher, kernel = _make_dispatcher(head=head, reply=reply, backend=_stub_pane_and_backend)

    preparation_service._deliver_cmd_replies(dispatcher)
    assert len(_stub_pane_and_backend.injected) == 1

    # Manually evict the cache to simulate aging out.
    cache = preparation_service._get_injected_cache(dispatcher)
    cache.clear()

    preparation_service._deliver_cmd_replies(dispatcher)
    assert len(_stub_pane_and_backend.injected) == 2, (
        'after cache eviction, the same reply may be re-injected (at-least-once delivery)'
    )
    assert kernel.calls == []
