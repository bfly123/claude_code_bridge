from __future__ import annotations

import json
from pathlib import Path
import socket
import threading
import time
from types import SimpleNamespace

import pytest

from agents.models import AgentRuntime, AgentState, AgentRestoreState, RestoreMode
from agents.store import AgentRuntimeStore
from ccbd.api_models import DeliveryScope, MessageEnvelope
from ccbd.app import CcbdApp
from ccbd.services.project_namespace_state import ProjectNamespaceEvent, ProjectNamespaceState
from ccbd.socket_client import CcbdClient, CcbdClientError
from ccbd.socket_server import CcbdSocketServer
from completion.models import CompletionConfidence, CompletionDecision, CompletionStatus
from message_bureau import AttemptStore, MessageStore
from mailbox_kernel import InboundEventStatus, InboundEventStore, InboundEventType
from project.ids import compute_project_id
from project.resolver import ProjectContext


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _agent_config_text(*pairs: tuple[str, str]) -> str:
    return ','.join(f'{agent_name}:{provider}' for agent_name, provider in pairs) + '\n'


def _single_agent_config_text(agent_name: str, provider: str) -> str:
    return _agent_config_text((agent_name, provider))


def _prepare_project(project_root: Path, config_text: str):
    project_root.mkdir()
    config_dir = project_root / '.ccb'
    _write(config_dir / 'ccb.config', config_text)
    return ProjectContext(
        cwd=project_root,
        project_root=project_root,
        config_dir=config_dir,
        project_id=compute_project_id(project_root),
        source='test',
    )


def _runtime(agent_name: str, *, project_id: str, workspace_path: str, pid: int) -> AgentRuntime:
    return AgentRuntime(
        agent_name=agent_name,
        state=AgentState.IDLE,
        pid=pid,
        started_at='2026-03-18T00:00:00Z',
        last_seen_at='2026-03-18T00:00:00Z',
        runtime_ref=f'{agent_name}-runtime',
        session_ref=f'{agent_name}-session',
        workspace_path=workspace_path,
        project_id=project_id,
        backend_type='tmux',
        queue_depth=0,
        socket_path=None,
        health='healthy',
    )


def _wait_for(path: Path, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            return
        time.sleep(0.02)
    raise AssertionError(f'timed out waiting for {path}')


def _wait_for_job_status(client: CcbdClient, job_id: str, expected: str, *, timeout: float = 3.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = client.get(job_id)
        if last['status'] == expected:
            return last
        time.sleep(0.05)
    raise AssertionError(f'expected job {job_id} status={expected!r}; last={last!r}')


def _decision(*, status: CompletionStatus = CompletionStatus.COMPLETED, reply: str = 'done') -> CompletionDecision:
    return CompletionDecision(
        terminal=True,
        status=status,
        reason='task_complete' if status is CompletionStatus.COMPLETED else status.value,
        confidence=CompletionConfidence.EXACT,
        reply=reply,
        anchor_seen=True,
        reply_started=True,
        reply_stable=True,
        provider_turn_ref='turn-1',
        source_cursor=None,
        finished_at='2026-03-18T00:00:10Z',
        diagnostics={},
    )


def _freeze_next_job_id(app: CcbdApp, monkeypatch: pytest.MonkeyPatch, job_id: str) -> None:
    original_new_id = app.dispatcher._new_id

    def _new_id(kind: str) -> str:
        if kind == 'job':
            return job_id
        return original_new_id(kind)

    monkeypatch.setattr(app.dispatcher, '_new_id', _new_id)


def test_ccbd_socket_roundtrip_and_shutdown(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    ctx = _prepare_project(project_root, _single_agent_config_text('codex', 'codex'))
    app = CcbdApp(project_root)
    app.registry.upsert(
        _runtime(
            'codex',
            project_id=ctx.project_id,
            workspace_path=str(app.paths.workspace_path('codex')),
            pid=777,
        )
    )

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    ping = client.ping('codex')
    assert ping['agent_name'] == 'codex'
    assert ping['provider'] == 'codex'

    submit = client.submit(
        MessageEnvelope(
            project_id=ctx.project_id,
            to_agent='codex',
            from_actor='user',
            body='hello',
            task_id='task-1',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']
    app.dispatcher.tick()
    running = client.get(job_id)
    assert running['status'] == 'running'

    app.dispatcher.complete(
        job_id,
        CompletionDecision(
            terminal=True,
            status=CompletionStatus.COMPLETED,
            reason='task_complete',
            confidence=CompletionConfidence.EXACT,
            reply='done',
            anchor_seen=True,
            reply_started=True,
            reply_stable=True,
            provider_turn_ref='turn-1',
            source_cursor=None,
            finished_at='2026-03-18T00:00:10Z',
            diagnostics={},
        ),
    )
    completed = client.get(job_id)
    assert completed['status'] == 'completed'
    assert completed['reply'] == 'done'
    assert completed['generation'] == 1
    completed_again = client.get(job_id)
    assert completed_again['status'] == 'completed'
    assert completed_again['reply'] == 'done'
    assert completed_again['completion_reason'] == 'task_complete'
    assert completed_again['completion_confidence'] == 'exact'

    watch = client.watch(job_id)
    assert watch['terminal'] is True
    assert watch['generation'] == 1
    event_types = [event['type'] for event in watch['events']]
    assert event_types[:2] == ['job_accepted', 'job_started']
    assert 'completion_terminal' in event_types
    assert event_types[-1] == 'job_completed'
    watch_again = client.watch(job_id)
    assert watch_again['terminal'] is True
    assert watch_again['reply'] == 'done'

    queue_all = client.queue('all')
    assert queue_all['target'] == 'all'
    assert queue_all['agent_count'] >= 1

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert app.mount_manager.load_state().mount_state.value == 'unmounted'


def test_ccbd_socket_shutdown_does_not_remove_replaced_socket_path(tmp_path: Path) -> None:
    socket_path = tmp_path / 'ccbd.sock'
    old_server = CcbdSocketServer(socket_path)
    old_server.listen()
    old_stat = socket_path.stat()

    socket_path.unlink()

    new_server = CcbdSocketServer(socket_path)
    new_server.listen()
    new_stat = socket_path.stat()

    assert (old_stat.st_dev, old_stat.st_ino) != (new_stat.st_dev, new_stat.st_ino)

    old_server.shutdown()
    assert socket_path.exists()
    current_stat = socket_path.stat()
    assert (current_stat.st_dev, current_stat.st_ino) == (new_stat.st_dev, new_stat.st_ino)

    new_server.shutdown()
    assert not socket_path.exists()


def test_ccbd_stop_all_does_not_run_post_shutdown_heartbeat(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-stop-all'
    ctx = _prepare_project(project_root, _single_agent_config_text('demo', 'fake'))
    app = CcbdApp(project_root)
    app.project_namespace.ensure = lambda: SimpleNamespace(  # type: ignore[method-assign]
        tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
        tmux_session_name=app.paths.ccbd_tmux_session_name,
        namespace_epoch=1,
    )
    app.project_namespace.destroy = lambda **kwargs: SimpleNamespace(destroyed=True, namespace_epoch=1)  # type: ignore[method-assign]

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    started = client.start(agent_names=('demo',), restore=False, auto_permission=False)
    assert started['started'] == ['demo']
    assert app.start_policy_store.load() is not None

    stopped = client.stop_all(force=False)
    assert stopped['state'] == 'unmounted'

    thread.join(timeout=2)
    assert not thread.is_alive()

    runtime = AgentRuntimeStore(app.paths).load('demo')
    assert runtime is not None
    assert runtime.state is AgentState.STOPPED
    assert runtime.desired_state == 'stopped'
    assert runtime.reconcile_state == 'stopped'
    assert runtime.runtime_ref is None
    assert runtime.session_ref is None
    assert ctx.project_id == runtime.project_id
    assert app.start_policy_store.load() is None


def test_ping_namespace_summary(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-ping-namespace'
    ctx = _prepare_project(project_root, _single_agent_config_text('codex', 'codex'))
    app = CcbdApp(project_root)
    app.namespace_state_store.save(
        ProjectNamespaceState(
            project_id=ctx.project_id,
            namespace_epoch=4,
            tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
            tmux_session_name=app.paths.ccbd_tmux_session_name,
            layout_version=1,
            ui_attachable=True,
            last_started_at='2026-04-03T00:05:00Z',
        )
    )
    app.namespace_event_store.append(
        ProjectNamespaceEvent(
            event_kind='namespace_created',
            project_id=ctx.project_id,
            occurred_at='2026-04-03T00:05:00Z',
            namespace_epoch=4,
            tmux_socket_path=str(app.paths.ccbd_tmux_socket_path),
            tmux_session_name=app.paths.ccbd_tmux_session_name,
        )
    )
    app.persist_start_policy(auto_permission=True)

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    ping = client.ping('ccbd')

    assert ping['namespace_epoch'] == 4
    assert ping['namespace_tmux_socket_path'] == str(app.paths.ccbd_tmux_socket_path)
    assert ping['namespace_tmux_session_name'] == app.paths.ccbd_tmux_session_name
    assert ping['namespace_last_event_kind'] == 'namespace_created'
    assert ping['start_policy_auto_permission'] is True
    assert ping['start_policy_recovery_restore'] is True

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_start_persists_policy(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-start-policy'
    _prepare_project(project_root, _single_agent_config_text('demo', 'fake'))
    app = CcbdApp(project_root)
    monkeypatch.setattr(
        app.runtime_supervisor,
        'start',
        lambda **kwargs: SimpleNamespace(
            to_record=lambda: {
                'project_root': str(project_root),
                'project_id': app.project_id,
                'started': ['demo'],
                'socket_path': str(app.paths.ccbd_socket_path),
            }
        ),
    )

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    started = client.start(agent_names=('demo',), restore=False, auto_permission=True)

    assert started['started'] == ['demo']
    policy = app.start_policy_store.load()
    assert policy is not None
    assert policy.auto_permission is True
    assert policy.recovery_restore is True
    assert policy.source == 'start_command'

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()

def test_ccbd_attach_and_restore_roundtrip(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    ctx = _prepare_project(project_root, _single_agent_config_text('codex', 'codex'))
    app = CcbdApp(project_root)
    app.restore_store.save(
        'codex',
        AgentRestoreState(
            restore_mode=RestoreMode.AUTO,
            last_checkpoint='checkpoint-1',
            conversation_summary='remember this state',
            open_tasks=['continue'],
            files_touched=['README.md'],
        ),
    )

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    attached = client.attach(
        agent_name='codex',
        workspace_path=str(app.paths.workspace_path('codex')),
        backend_type='pane-backed',
        runtime_ref='codex:codex:attached',
        session_ref='session:codex',
    )
    assert attached['agent_name'] == 'codex'
    assert attached['health'] == 'healthy'
    assert attached['binding_source'] == 'external-attach'

    restored = client.restore('codex')
    assert restored['last_restore_status'] == 'checkpoint'
    reattached = client.attach(
        agent_name='codex',
        workspace_path=str(app.paths.workspace_path('codex')),
        backend_type='pane-backed',
        runtime_ref='tmux:%88',
        session_ref='session:codex:new',
    )
    assert reattached['runtime_ref'] == 'tmux:%88'
    assert reattached['session_ref'] == 'session:codex:new'
    runtime = app.registry.get('codex')
    assert runtime is not None
    assert runtime.health == 'restored'
    assert runtime.runtime_ref == 'tmux:%88'
    assert runtime.session_ref == 'session:codex:new'
    assert runtime.binding_source.value == 'external-attach'

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_queue_reports_registered_agent_mailboxes(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-queue'
    ctx = _prepare_project(
        project_root,
        _agent_config_text(('codex', 'codex'), ('claude', 'claude')),
    )
    app = CcbdApp(project_root)
    app.registry.upsert(
        _runtime(
            'codex',
            project_id=ctx.project_id,
            workspace_path=str(app.paths.workspace_path('codex')),
            pid=777,
        )
    )
    app.registry.upsert(
        _runtime(
            'claude',
            project_id=ctx.project_id,
            workspace_path=str(app.paths.workspace_path('claude')),
            pid=778,
        )
    )

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    submit = client.submit(
        MessageEnvelope(
            project_id=ctx.project_id,
            to_agent='codex',
            from_actor='claude',
            body='hello queue',
            task_id='task-queue',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']
    app.dispatcher.tick()

    running_queue = client.queue('codex')
    assert running_queue['target'] == 'codex'
    assert running_queue['agent']['mailbox_state'] == 'delivering'
    assert running_queue['agent']['active']['job_id'] == job_id

    app.dispatcher.complete(job_id, _decision(reply='done queue'))

    reply_queue = client.queue('claude')
    assert reply_queue['target'] == 'claude'
    assert reply_queue['agent']['pending_reply_count'] == 1
    assert reply_queue['agent']['queued_events'][0]['event_type'] == 'task_reply'

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_trace_returns_attempt_reply_and_mailbox_events(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-trace'
    ctx = _prepare_project(
        project_root,
        _agent_config_text(('codex', 'codex'), ('claude', 'claude')),
    )
    app = CcbdApp(project_root)
    app.registry.upsert(
        _runtime(
            'codex',
            project_id=ctx.project_id,
            workspace_path=str(app.paths.workspace_path('codex')),
            pid=777,
        )
    )
    app.registry.upsert(
        _runtime(
            'claude',
            project_id=ctx.project_id,
            workspace_path=str(app.paths.workspace_path('claude')),
            pid=778,
        )
    )

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    submit = client.submit(
        MessageEnvelope(
            project_id=ctx.project_id,
            to_agent='codex',
            from_actor='claude',
            body='hello trace',
            task_id='task-trace',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']
    app.dispatcher.tick()
    app.dispatcher.complete(job_id, _decision(reply='trace done'))

    payload = client.trace(job_id)

    assert payload['target'] == job_id
    assert payload['resolved_kind'] == 'job'
    assert payload['job_id'] == job_id
    assert payload['message_count'] == 1
    assert payload['attempt_count'] == 1
    assert payload['reply_count'] == 1
    assert payload['event_count'] == 2
    assert payload['job_count'] == 1
    assert payload['messages'][0]['from_actor'] == 'claude'
    assert payload['attempts'][0]['job_id'] == job_id
    assert payload['replies'][0]['reply_preview'] == 'trace done'
    assert {item['event_type'] for item in payload['events']} == {'task_request', 'task_reply'}

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_inbox_and_ack_roundtrip_reply_delivery(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-inbox-ack'
    ctx = _prepare_project(
        project_root,
        _agent_config_text(('codex', 'codex'), ('claude', 'claude')),
    )
    app = CcbdApp(project_root)
    app.registry.upsert(
        _runtime(
            'codex',
            project_id=ctx.project_id,
            workspace_path=str(app.paths.workspace_path('codex')),
            pid=777,
        )
    )
    app.registry.upsert(
        _runtime(
            'claude',
            project_id=ctx.project_id,
            workspace_path=str(app.paths.workspace_path('claude')),
            pid=778,
        )
    )

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    submit = client.submit(
        MessageEnvelope(
            project_id=ctx.project_id,
            to_agent='codex',
            from_actor='claude',
            body='hello inbox',
            task_id='task-inbox-ack',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']
    app.dispatcher.tick()
    app.dispatcher.complete(job_id, _decision(reply='socket inbox reply'))

    inbox = client.inbox('claude')
    assert inbox['target'] == 'claude'
    assert inbox['head']['event_type'] == 'task_reply'
    assert inbox['head']['reply'] == 'socket inbox reply'

    with pytest.raises(CcbdClientError, match='automatic reply delivery has been scheduled'):
        client.ack('claude')

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_cmd_sender_routes_reply_into_cmd_mailbox(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-inbox-ack-cmd'
    ctx = _prepare_project(
        project_root,
        'cmd; codex:codex,claude:claude\n',
    )
    app = CcbdApp(project_root)
    app.registry.upsert(
        _runtime(
            'codex',
            project_id=ctx.project_id,
            workspace_path=str(app.paths.workspace_path('codex')),
            pid=777,
        )
    )

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    submit = client.submit(
        MessageEnvelope(
            project_id=ctx.project_id,
            to_agent='codex',
            from_actor='cmd',
            body='hello cmd inbox',
            task_id='task-inbox-cmd',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']
    app.dispatcher.tick()
    app.dispatcher.complete(job_id, _decision(reply='socket cmd reply'))

    completed = client.get(job_id)
    assert completed['status'] == 'completed'
    assert completed['reply'] == 'socket cmd reply'

    inbox = client.inbox('cmd')
    assert inbox['target'] == 'cmd'
    assert inbox['head']['event_type'] == 'task_reply'
    assert inbox['head']['reply'] == 'socket cmd reply'

    queue = client.queue('all')
    assert {item['agent_name'] for item in queue['agents']} == {'claude', 'cmd', 'codex'}

    ack = client.ack('cmd')
    assert ack['target'] == 'cmd'
    assert ack['reply'] == 'socket cmd reply'
    assert ack['acknowledged_inbound_event_id']

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_resubmit_creates_new_message_record_with_origin(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-resubmit-socket'
    ctx = _prepare_project(project_root, _single_agent_config_text('codex', 'codex'))
    app = CcbdApp(project_root)
    app.registry.upsert(
        _runtime(
            'codex',
            project_id=ctx.project_id,
            workspace_path=str(app.paths.workspace_path('codex')),
            pid=777,
        )
    )

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    submit = client.submit(
        MessageEnvelope(
            project_id=ctx.project_id,
            to_agent='codex',
            from_actor='user',
            body='hello resubmit',
            task_id='task-resubmit-socket',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']
    _wait_for_job_status(client, job_id, 'running')
    app.dispatcher.complete(job_id, _decision(status=CompletionStatus.INCOMPLETE, reply='retry me'))
    _wait_for_job_status(client, job_id, 'incomplete')

    original_message = MessageStore(app.paths).list_all()[-1]
    payload = client.resubmit(original_message.message_id)

    assert payload['original_message_id'] == original_message.message_id
    assert payload['message_id'] != original_message.message_id
    assert len(payload['jobs']) == 1
    assert payload['jobs'][0]['agent_name'] == 'codex'

    new_message = MessageStore(app.paths).get_latest(payload['message_id'])
    assert new_message is not None
    assert new_message.origin_message_id == original_message.message_id

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_retry_creates_new_attempt_under_existing_message(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-retry-socket'
    ctx = _prepare_project(project_root, _single_agent_config_text('codex', 'codex'))
    app = CcbdApp(project_root)
    app.registry.upsert(
        _runtime(
            'codex',
            project_id=ctx.project_id,
            workspace_path=str(app.paths.workspace_path('codex')),
            pid=777,
        )
    )

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    submit = client.submit(
        MessageEnvelope(
            project_id=ctx.project_id,
            to_agent='codex',
            from_actor='user',
            body='hello retry',
            task_id='task-retry-socket',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']
    _wait_for_job_status(client, job_id, 'running')
    app.dispatcher.complete(job_id, _decision(status=CompletionStatus.INCOMPLETE, reply='retry me'))
    _wait_for_job_status(client, job_id, 'incomplete')

    original_message = MessageStore(app.paths).list_all()[-1]
    original_attempt = AttemptStore(app.paths).get_latest_by_job_id(job_id)
    assert original_attempt is not None

    payload = client.retry(job_id)

    assert payload['target'] == job_id
    assert payload['message_id'] == original_message.message_id
    assert payload['original_attempt_id'] == original_attempt.attempt_id
    assert payload['attempt_id'] != original_attempt.attempt_id
    assert payload['job_id'] != job_id
    assert payload['agent_name'] == 'codex'

    new_attempt = AttemptStore(app.paths).get_latest(payload['attempt_id'])
    assert new_attempt is not None
    assert new_attempt.message_id == original_message.message_id
    assert new_attempt.retry_index == 1

    codex_events = InboundEventStore(app.paths).list_agent('codex')
    assert codex_events[-1].attempt_id == payload['attempt_id']
    assert codex_events[-1].event_type is InboundEventType.TASK_REQUEST
    assert codex_events[-1].status is InboundEventStatus.QUEUED

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_ignores_client_disconnect_during_response(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-broken-pipe'
    _prepare_project(project_root, _single_agent_config_text('codex', 'codex'))
    app = CcbdApp(project_root)

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(str(app.paths.ccbd_socket_path))
    sock.sendall((json.dumps({'api_version': 2, 'op': 'ping', 'request': {'target': 'ccbd'}}) + '\n').encode('utf-8'))
    sock.close()

    time.sleep(0.1)

    client = CcbdClient(app.paths.ccbd_socket_path)
    ping = client.ping('ccbd')
    assert ping['mount_state'] == 'mounted'

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_attach_without_provider_binding_does_not_synthesize_refs(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-unbound'
    _prepare_project(project_root, _single_agent_config_text('codex', 'codex'))
    app = CcbdApp(project_root)
    app.restore_store.save(
        'codex',
        AgentRestoreState(
            restore_mode=RestoreMode.AUTO,
            last_checkpoint='checkpoint-1',
            conversation_summary='remember this state',
            open_tasks=['continue'],
            files_touched=['README.md'],
        ),
    )

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    attached = client.attach(
        agent_name='codex',
        workspace_path=str(app.paths.workspace_path('codex')),
        backend_type='pane-backed',
    )
    assert attached['runtime_ref'] is None
    assert attached['session_ref'] is None

    restored = client.restore('codex')
    assert restored['last_restore_status'] == 'checkpoint'
    runtime = app.registry.get('codex')
    assert runtime is not None
    assert runtime.health == 'restored'
    assert runtime.runtime_ref is None
    assert runtime.session_ref is None

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_attach_empty_binding_fields_clear_previous_refs(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-clear-binding'
    ctx = _prepare_project(project_root, _single_agent_config_text('codex', 'codex'))
    app = CcbdApp(project_root)

    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    client.attach(
        agent_name='codex',
        workspace_path=str(app.paths.workspace_path('codex')),
        backend_type='pane-backed',
        runtime_ref='tmux:%88',
        session_ref='session:codex:new',
        health='healthy',
    )

    cleared = client.attach(
        agent_name='codex',
        workspace_path=str(app.paths.workspace_path('codex')),
        backend_type='pane-backed',
        runtime_ref='',
        session_ref='',
        health='degraded',
    )

    assert cleared['runtime_ref'] is None
    assert cleared['session_ref'] is None
    assert cleared['health'] == 'degraded'
    runtime = app.registry.get('codex')
    assert runtime is not None
    assert runtime.runtime_ref is None
    assert runtime.session_ref is None
    assert runtime.health == 'degraded'

    client.shutdown()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_codex_protocol_turn_completes_via_tracker(monkeypatch, tmp_path: Path) -> None:
    from provider_execution import codex as codex_adapter_module

    fixed_req_id = 'job_codex1'
    sent: list[tuple[str, str]] = []
    project_root = tmp_path / 'repo-codex'
    _write(project_root / '.ccb' / 'ccb.config', _single_agent_config_text('demo', 'codex'))

    class FakeBackend:
        def send_text(self, pane_id: str, text: str) -> None:
            sent.append((pane_id, text))

        def is_alive(self, pane_id: str) -> bool:
            return pane_id == '%1'

    class FakeSession:
        data = {}
        codex_session_path = str(tmp_path / 'demo-session.jsonl')
        codex_session_id = 'demo-session-id'
        work_dir = str(project_root)

        def ensure_pane(self):
            return True, '%1'

    class FakeReader:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs
            self._events = [
                {
                    'role': 'user',
                    'text': f'CCB_REQ_ID: {fixed_req_id}\n\nprompt',
                    'entry_type': 'response_item',
                    'payload_type': 'message',
                    'timestamp': '2026-03-18T00:00:00Z',
                },
                {
                    'role': 'assistant',
                    'text': 'partial',
                    'entry_type': 'event_msg',
                    'payload_type': 'agent_message',
                    'timestamp': '2026-03-18T00:00:01Z',
                },
                {
                    'role': 'assistant',
                    'text': 'final without done',
                    'entry_type': 'event_msg',
                    'payload_type': 'agent_message',
                    'phase': 'final_answer',
                    'timestamp': '2026-03-18T00:00:02Z',
                },
                {
                    'role': 'assistant',
                    'text': 'final without done',
                    'entry_type': 'response_item',
                    'payload_type': 'message',
                    'phase': 'final_answer',
                    'timestamp': '2026-03-18T00:00:02Z',
                },
                {
                    'role': 'system',
                    'text': 'partial\nfinal without done',
                    'entry_type': 'event_msg',
                    'payload_type': 'task_complete',
                    'turn_id': 'turn-codex-socket',
                    'last_agent_message': 'partial\nfinal without done',
                    'timestamp': '2026-03-18T00:00:03Z',
                },
            ]

        def capture_state(self):
            return {'index': 0}

        def try_get_entries(self, state):
            index = int(state.get('index', 0))
            if index >= len(self._events):
                return [], state
            return [self._events[index]], {'index': index + 1}

    monkeypatch.setattr(codex_adapter_module, 'load_project_session', lambda work_dir, instance=None: FakeSession())
    monkeypatch.setattr(codex_adapter_module, 'get_backend_for_session', lambda data: FakeBackend())
    monkeypatch.setattr(codex_adapter_module, 'CodexLogReader', FakeReader)

    app = CcbdApp(project_root)
    _freeze_next_job_id(app, monkeypatch, fixed_req_id)
    app.paths.workspace_path('demo').mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    attached = client.attach(
        agent_name='demo',
        workspace_path=str(app.paths.workspace_path('demo')),
        backend_type='pane-backed',
        runtime_ref='tmux:%1',
        session_ref='demo-session-id',
    )
    assert attached['agent_name'] == 'demo'

    submit = client.submit(
        MessageEnvelope(
            project_id=app.project_id,
            to_agent='demo',
            from_actor='user',
            body='hello codex',
            task_id='task-codex',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']

    completed = _wait_for_job_status(client, job_id, 'completed', timeout=3.0)
    assert completed['reply'] == 'partial\nfinal without done'
    assert completed['completion_reason'] == 'task_complete'
    assert completed['completion_confidence'] == 'exact'
    assert sent and sent[0][0] == '%1'
    assert fixed_req_id in sent[0][1]
    assert 'CCB_DONE:' not in sent[0][1]

    watch = client.watch(job_id)
    assert watch['terminal'] is True
    event_types = [event['type'] for event in watch['events']]
    assert event_types.count('completion_item') == 4
    assert 'completion_state_updated' in event_types
    assert 'completion_terminal' in event_types
    assert event_types[-1] == 'job_completed'

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_codex_protocol_turn_handles_interrupted_abort(monkeypatch, tmp_path: Path) -> None:
    from provider_execution import codex as codex_adapter_module

    fixed_req_id = 'job_codex2'
    sent: list[tuple[str, str]] = []
    project_root = tmp_path / 'repo-codex-abort'
    _write(project_root / '.ccb' / 'ccb.config', _single_agent_config_text('demo', 'codex'))

    class FakeBackend:
        def send_text(self, pane_id: str, text: str) -> None:
            sent.append((pane_id, text))

        def is_alive(self, pane_id: str) -> bool:
            return pane_id == '%1'

    class FakeSession:
        data = {}
        codex_session_path = str(tmp_path / 'demo-session.jsonl')
        codex_session_id = 'demo-session-id'
        work_dir = str(project_root)

        def ensure_pane(self):
            return True, '%1'

    class FakeReader:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs
            self._events = [
                {
                    'role': 'user',
                    'text': f'CCB_REQ_ID: {fixed_req_id}\n\nprompt',
                    'entry_type': 'response_item',
                    'payload_type': 'message',
                    'timestamp': '2026-03-18T00:00:00Z',
                },
                {
                    'role': 'assistant',
                    'text': 'partial before interrupt',
                    'entry_type': 'event_msg',
                    'payload_type': 'agent_message',
                    'timestamp': '2026-03-18T00:00:01Z',
                },
                {
                    'role': 'system',
                    'text': '',
                    'entry_type': 'event_msg',
                    'payload_type': 'turn_aborted',
                    'turn_id': 'turn-codex-abort',
                    'reason': 'interrupted',
                    'timestamp': '2026-03-18T00:00:02Z',
                },
            ]

        def capture_state(self):
            return {'index': 0}

        def try_get_entries(self, state):
            index = int(state.get('index', 0))
            if index >= len(self._events):
                return [], state
            return [self._events[index]], {'index': index + 1}

    monkeypatch.setattr(codex_adapter_module, 'load_project_session', lambda work_dir, instance=None: FakeSession())
    monkeypatch.setattr(codex_adapter_module, 'get_backend_for_session', lambda data: FakeBackend())
    monkeypatch.setattr(codex_adapter_module, 'CodexLogReader', FakeReader)

    app = CcbdApp(project_root)
    _freeze_next_job_id(app, monkeypatch, fixed_req_id)
    app.paths.workspace_path('demo').mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    client.attach(
        agent_name='demo',
        workspace_path=str(app.paths.workspace_path('demo')),
        backend_type='pane-backed',
        runtime_ref='tmux:%1',
        session_ref='demo-session-id',
    )

    submit = client.submit(
        MessageEnvelope(
            project_id=app.project_id,
            to_agent='demo',
            from_actor='user',
            body='interrupt codex',
            task_id='task-codex-abort',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']

    cancelled = _wait_for_job_status(client, job_id, 'cancelled', timeout=3.0)
    assert cancelled['reply'] == 'partial before interrupt'
    assert cancelled['completion_reason'] == 'interrupted'
    assert cancelled['completion_confidence'] == 'exact'
    assert sent and sent[0][0] == '%1'
    assert fixed_req_id in sent[0][1]
    assert 'CCB_DONE:' not in sent[0][1]

    watch = client.watch(job_id)
    assert watch['terminal'] is True
    event_types = [event['type'] for event in watch['events']]
    assert 'completion_terminal' in event_types
    assert event_types[-1] == 'job_cancelled'

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_claude_session_boundary_completes_via_tracker(monkeypatch, tmp_path: Path) -> None:
    from provider_execution import claude as claude_adapter_module

    fixed_req_id = 'job_claude1'
    sent: list[tuple[str, str]] = []
    project_root = tmp_path / 'repo-claude'
    _write(project_root / '.ccb' / 'ccb.config', _single_agent_config_text('demo', 'claude'))

    class FakeBackend:
        def send_text(self, pane_id: str, text: str) -> None:
            sent.append((pane_id, text))

        def is_alive(self, pane_id: str) -> bool:
            return pane_id == '%2'

    class FakeSession:
        data = {}
        claude_session_path = str(tmp_path / 'claude-session.jsonl')
        claude_session_id = 'claude-session-id'
        claude_projects_root = None
        work_dir = str(project_root)

        def ensure_pane(self):
            return True, '%2'

    class FakeReader:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs
            self._events = [
                ('user', f'CCB_REQ_ID: {fixed_req_id}\n\nprompt'),
                ('assistant', 'partial'),
                ('assistant', f'final\nCCB_DONE: {fixed_req_id}'),
            ]

        def set_preferred_session(self, session_path) -> None:
            del session_path

        def capture_state(self):
            return {'session_path': str(tmp_path / 'claude-session.jsonl'), 'offset': 0}

        def try_get_events(self, state):
            index = int(state.get('index', 0))
            if index >= len(self._events):
                return [], state
            return [self._events[index]], {**state, 'index': index + 1}

    monkeypatch.setattr(claude_adapter_module, 'load_project_session', lambda work_dir, instance=None: FakeSession())
    monkeypatch.setattr(claude_adapter_module, 'get_backend_for_session', lambda data: FakeBackend())
    monkeypatch.setattr(claude_adapter_module, 'ClaudeLogReader', FakeReader)

    app = CcbdApp(project_root)
    _freeze_next_job_id(app, monkeypatch, fixed_req_id)
    app.paths.workspace_path('demo').mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    attached = client.attach(
        agent_name='demo',
        workspace_path=str(app.paths.workspace_path('demo')),
        backend_type='pane-backed',
        runtime_ref='tmux:%2',
        session_ref='claude-session-id',
    )
    assert attached['agent_name'] == 'demo'

    submit = client.submit(
        MessageEnvelope(
            project_id=app.project_id,
            to_agent='demo',
            from_actor='user',
            body='hello claude',
            task_id='task-claude',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']

    completed = _wait_for_job_status(client, job_id, 'completed', timeout=3.0)
    assert completed['reply'] == 'partial\nfinal'
    assert completed['completion_reason'] == 'task_complete'
    assert completed['completion_confidence'] == 'observed'
    assert sent and sent[0][0] == '%2'
    assert fixed_req_id in sent[0][1]

    watch = client.watch(job_id)
    assert watch['terminal'] is True
    event_types = [event['type'] for event in watch['events']]
    assert event_types.count('completion_item') == 4
    assert 'completion_state_updated' in event_types
    assert 'completion_terminal' in event_types
    assert event_types[-1] == 'job_completed'

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_claude_turn_duration_completion_without_done_marker(monkeypatch, tmp_path: Path) -> None:
    from provider_execution import claude as claude_adapter_module

    fixed_req_id = 'job_claude2'
    sent: list[tuple[str, str]] = []
    project_root = tmp_path / 'repo-claude-td'
    _write(project_root / '.ccb' / 'ccb.config', _single_agent_config_text('demo', 'claude'))

    class FakeBackend:
        def send_text(self, pane_id: str, text: str) -> None:
            sent.append((pane_id, text))

        def is_alive(self, pane_id: str) -> bool:
            return pane_id == '%2'

    class FakeSession:
        data = {}
        claude_session_path = str(tmp_path / 'claude-session.jsonl')
        claude_session_id = 'claude-session-id'
        claude_projects_root = None
        work_dir = str(project_root)

        def ensure_pane(self):
            return True, '%2'

    class FakeReader:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs
            self._events = [
                {'role': 'user', 'text': f'CCB_REQ_ID: {fixed_req_id}\n\nprompt', 'entry_type': 'user'},
                {'role': 'assistant', 'text': 'final without done', 'entry_type': 'assistant', 'uuid': 'assistant-1'},
                {'role': 'system', 'text': '', 'entry_type': 'system', 'subtype': 'turn_duration', 'parent_uuid': 'assistant-1'},
            ]

        def set_preferred_session(self, session_path) -> None:
            del session_path

        def capture_state(self):
            return {'session_path': str(tmp_path / 'claude-session.jsonl'), 'offset': 0}

        def try_get_entries(self, state):
            index = int(state.get('index', 0))
            if index >= len(self._events):
                return [], state
            return [self._events[index]], {**state, 'index': index + 1}

    monkeypatch.setattr(claude_adapter_module, 'load_project_session', lambda work_dir, instance=None: FakeSession())
    monkeypatch.setattr(claude_adapter_module, 'get_backend_for_session', lambda data: FakeBackend())
    monkeypatch.setattr(claude_adapter_module, 'ClaudeLogReader', FakeReader)

    app = CcbdApp(project_root)
    _freeze_next_job_id(app, monkeypatch, fixed_req_id)
    app.paths.workspace_path('demo').mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    client.attach(
        agent_name='demo',
        workspace_path=str(app.paths.workspace_path('demo')),
        backend_type='pane-backed',
        runtime_ref='tmux:%2',
        session_ref='claude-session-id',
    )

    submit = client.submit(
        MessageEnvelope(
            project_id=app.project_id,
            to_agent='demo',
            from_actor='user',
            body='hello claude',
            task_id='task-claude-turn',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']

    completed = _wait_for_job_status(client, job_id, 'completed', timeout=3.0)
    assert completed['reply'] == 'final without done'
    assert completed['completion_reason'] == 'turn_duration'
    assert completed['completion_confidence'] == 'observed'
    assert sent and sent[0][0] == '%2'
    assert fixed_req_id in sent[0][1]

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_gemini_session_snapshot_completes_via_tracker(monkeypatch, tmp_path: Path) -> None:
    from provider_execution import gemini as gemini_adapter_module

    fixed_req_id = 'job_gemini1'
    sent: list[tuple[str, str]] = []
    project_root = tmp_path / 'repo-gemini'
    _write(project_root / '.ccb' / 'ccb.config', _single_agent_config_text('demo', 'gemini'))

    class FakeBackend:
        def send_text(self, pane_id: str, text: str) -> None:
            sent.append((pane_id, text))

        def is_alive(self, pane_id: str) -> bool:
            return pane_id == '%3'

    class FakeSession:
        data = {}
        gemini_session_path = str(tmp_path / 'gemini-session.json')
        gemini_session_id = 'gemini-session-id'
        work_dir = str(project_root)

        def ensure_pane(self):
            return True, '%3'

    class FakeReader:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs
            self._emitted = False

        def set_preferred_session(self, session_path) -> None:
            del session_path

        def capture_state(self):
            return {'session_path': str(tmp_path / 'gemini-session.json'), 'msg_count': 0}

        def try_get_message(self, state):
            if self._emitted:
                return None, state
            self._emitted = True
            return (
                'stable reply',
                {
                    **state,
                    'msg_count': 2,
                    'last_gemini_id': 'msg-2',
                    'mtime_ns': 123456789,
                },
            )

    monkeypatch.setattr(gemini_adapter_module, 'load_project_session', lambda work_dir, instance=None: FakeSession())
    monkeypatch.setattr(gemini_adapter_module, 'get_backend_for_session', lambda data: FakeBackend())
    monkeypatch.setattr(gemini_adapter_module, 'GeminiLogReader', FakeReader)

    app = CcbdApp(project_root)
    _freeze_next_job_id(app, monkeypatch, fixed_req_id)
    app.paths.workspace_path('demo').mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    attached = client.attach(
        agent_name='demo',
        workspace_path=str(app.paths.workspace_path('demo')),
        backend_type='pane-backed',
        runtime_ref='tmux:%3',
        session_ref='gemini-session-id',
    )
    assert attached['agent_name'] == 'demo'

    submit = client.submit(
        MessageEnvelope(
            project_id=app.project_id,
            to_agent='demo',
            from_actor='user',
            body='hello gemini',
            task_id='task-gemini',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']

    completed = _wait_for_job_status(client, job_id, 'completed', timeout=5.0)
    assert completed['reply'] == 'stable reply'
    assert completed['completion_reason'] == 'session_reply_stable'
    assert completed['completion_confidence'] == 'observed'
    assert sent and sent[0][0] == '%3'
    assert fixed_req_id in sent[0][1]

    watch = client.watch(job_id)
    assert watch['terminal'] is True
    event_types = [event['type'] for event in watch['events']]
    assert event_types.count('completion_item') == 2
    assert 'completion_terminal' in event_types
    assert event_types[-1] == 'job_completed'

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_gemini_long_silence_and_session_rotate_do_not_finish_early(monkeypatch, tmp_path: Path) -> None:
    from provider_execution import gemini as gemini_adapter_module

    fixed_req_id = 'job_geminirotate'
    project_root = tmp_path / 'repo-gemini-rotate'
    _write(project_root / '.ccb' / 'ccb.config', _single_agent_config_text('demo', 'gemini'))

    class FakeBackend:
        def send_text(self, pane_id: str, text: str) -> None:
            del pane_id, text

        def is_alive(self, pane_id: str) -> bool:
            return pane_id == '%3'

    class FakeSession:
        data = {}
        gemini_session_path = str(tmp_path / 'gemini-session-old.json')
        gemini_session_id = 'gemini-session-id'
        work_dir = str(project_root)

        def ensure_pane(self):
            return True, '%3'

    class FakeReader:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs
            self._calls = 0
            self._emitted = False

        def set_preferred_session(self, session_path) -> None:
            del session_path

        def capture_state(self):
            return {'session_path': str(tmp_path / 'gemini-session-old.json'), 'msg_count': 0}

        def try_get_message(self, state):
            self._calls += 1
            if self._calls < 4 or self._emitted:
                return None, state
            self._emitted = True
            return (
                'rotated stable reply',
                {
                    **state,
                    'session_path': str(tmp_path / 'gemini-session-new.json'),
                    'msg_count': 4,
                    'last_gemini_id': 'msg-4',
                    'mtime_ns': 987654321,
                },
            )

    monkeypatch.setattr(gemini_adapter_module, 'load_project_session', lambda work_dir, instance=None: FakeSession())
    monkeypatch.setattr(gemini_adapter_module, 'get_backend_for_session', lambda data: FakeBackend())
    monkeypatch.setattr(gemini_adapter_module, 'GeminiLogReader', FakeReader)

    app = CcbdApp(project_root)
    _freeze_next_job_id(app, monkeypatch, fixed_req_id)
    app.paths.workspace_path('demo').mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    client.attach(
        agent_name='demo',
        workspace_path=str(app.paths.workspace_path('demo')),
        backend_type='pane-backed',
        runtime_ref='tmux:%3',
        session_ref='gemini-session-id',
    )

    submit = client.submit(
        MessageEnvelope(
            project_id=app.project_id,
            to_agent='demo',
            from_actor='user',
            body='hello rotate gemini',
            task_id='task-gemini-rotate',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']

    time.sleep(0.15)
    running = client.get(job_id)
    assert running['status'] == 'running'
    assert running['completion_reason'] is None

    completed = _wait_for_job_status(client, job_id, 'completed', timeout=5.0)
    assert completed['reply'] == 'rotated stable reply'
    assert completed['completion_reason'] == 'session_reply_stable'
    assert completed['completion_confidence'] == 'observed'

    watch = client.watch(job_id)
    assert watch['terminal'] is True
    event_types = [event['type'] for event in watch['events']]
    assert event_types.count('completion_item') == 4
    assert 'completion_terminal' in event_types
    assert event_types[-1] == 'job_completed'

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_gemini_tool_call_progress_does_not_finish_on_first_round(monkeypatch, tmp_path: Path) -> None:
    from provider_execution import gemini as gemini_adapter_module

    fixed_req_id = 'job_geminitoolwait'
    project_root = tmp_path / 'repo-gemini-toolwait'
    _write(project_root / '.ccb' / 'ccb.config', _single_agent_config_text('demo', 'gemini'))

    class FakeBackend:
        def send_text(self, pane_id: str, text: str) -> None:
            del pane_id, text

        def is_alive(self, pane_id: str) -> bool:
            return pane_id == '%3'

    class FakeSession:
        data = {}
        gemini_session_path = str(tmp_path / 'gemini-session.json')
        gemini_session_id = 'gemini-session-id'
        work_dir = str(project_root)

        def ensure_pane(self):
            return True, '%3'

    class FakeReader:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs
            self._calls = 0

        def set_preferred_session(self, session_path) -> None:
            del session_path

        def capture_state(self):
            return {'session_path': str(tmp_path / 'gemini-session.json'), 'msg_count': 0}

        def try_get_message(self, state):
            self._calls += 1
            if self._calls == 1:
                return (
                    'I will inspect the manuscript first.',
                    {
                        **state,
                        'msg_count': 1,
                        'last_gemini_id': 'msg-1',
                        'mtime_ns': 111,
                        'last_tool_call_count': 1,
                    },
                )
            if self._calls < 10:
                return None, state
            if self._calls == 10:
                return (
                    'Final review result.',
                    {
                        **state,
                        'msg_count': 2,
                        'last_gemini_id': 'msg-2',
                        'mtime_ns': 222,
                        'last_tool_call_count': 0,
                    },
                )
            return None, state

    monkeypatch.setattr(gemini_adapter_module, 'load_project_session', lambda work_dir, instance=None: FakeSession())
    monkeypatch.setattr(gemini_adapter_module, 'get_backend_for_session', lambda data: FakeBackend())
    monkeypatch.setattr(gemini_adapter_module, 'GeminiLogReader', FakeReader)

    app = CcbdApp(project_root)
    _freeze_next_job_id(app, monkeypatch, fixed_req_id)
    app.paths.workspace_path('demo').mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    client.attach(
        agent_name='demo',
        workspace_path=str(app.paths.workspace_path('demo')),
        backend_type='pane-backed',
        runtime_ref='tmux:%3',
        session_ref='gemini-session-id',
    )

    submit = client.submit(
        MessageEnvelope(
            project_id=app.project_id,
            to_agent='demo',
            from_actor='user',
            body='hello gemini tool progress',
            task_id='task-gemini-tool-progress',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']

    time.sleep(0.15)
    running = client.get(job_id)
    assert running['status'] == 'running'
    assert running['completion_reason'] is None
    assert running['reply'] == 'I will inspect the manuscript first.'

    completed = _wait_for_job_status(client, job_id, 'completed', timeout=5.0)
    assert completed['reply'] == 'Final review result.'
    assert completed['completion_reason'] == 'session_reply_stable'

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_gemini_rotate_clears_stale_reply_preview(monkeypatch, tmp_path: Path) -> None:
    from provider_execution import gemini as gemini_adapter_module

    fixed_req_id = 'job_geminipreview'
    project_root = tmp_path / 'gpr'
    _write(project_root / '.ccb' / 'ccb.config', _single_agent_config_text('demo', 'gemini'))

    class FakeBackend:
        def send_text(self, pane_id: str, text: str) -> None:
            del pane_id, text

        def is_alive(self, pane_id: str) -> bool:
            return pane_id == '%3'

    class FakeSession:
        data = {}
        gemini_session_path = str(tmp_path / 'gemini-session-old.json')
        gemini_session_id = 'gemini-session-id'
        work_dir = str(project_root)

        def ensure_pane(self):
            return True, '%3'

    class FakeReader:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs
            self._calls = 0

        def set_preferred_session(self, session_path) -> None:
            del session_path

        def capture_state(self):
            return {'session_path': str(tmp_path / 'gemini-session-old.json'), 'msg_count': 0}

        def try_get_message(self, state):
            self._calls += 1
            if self._calls == 1:
                return (
                    'old preview reply',
                    {
                        **state,
                        'msg_count': 1,
                        'last_gemini_id': 'msg-old',
                        'mtime_ns': 111,
                    },
                )
            if self._calls == 2:
                return (
                    None,
                    {
                        **state,
                        'session_path': str(tmp_path / 'gemini-session-new.json'),
                        'msg_count': 0,
                        'last_gemini_id': None,
                        'mtime_ns': 222,
                    },
                )
            return None, state

    monkeypatch.setattr(gemini_adapter_module, 'load_project_session', lambda work_dir, instance=None: FakeSession())
    monkeypatch.setattr(gemini_adapter_module, 'get_backend_for_session', lambda data: FakeBackend())
    monkeypatch.setattr(gemini_adapter_module, 'GeminiLogReader', FakeReader)

    app = CcbdApp(project_root)
    _freeze_next_job_id(app, monkeypatch, fixed_req_id)
    app.paths.workspace_path('demo').mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    client.attach(
        agent_name='demo',
        workspace_path=str(app.paths.workspace_path('demo')),
        backend_type='pane-backed',
        runtime_ref='tmux:%3',
        session_ref='gemini-session-id',
    )

    submit = client.submit(
        MessageEnvelope(
            project_id=app.project_id,
            to_agent='demo',
            from_actor='user',
            body='hello gemini rotate preview',
            task_id='task-gemini-preview-reset',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']

    time.sleep(0.25)
    running = client.get(job_id)
    assert running['status'] == 'running'
    assert running['reply'] == ''
    assert running['completion_reason'] is None

    watch = client.watch(job_id)
    assert watch['terminal'] is False
    completion_items = [event for event in watch['events'] if event['type'] == 'completion_item']
    assert len(completion_items) >= 4

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_opencode_completed_reply_uses_session_boundary_tracker(monkeypatch, tmp_path: Path) -> None:
    from provider_execution import opencode as opencode_adapter_module

    fixed_req_id = 'job_opencode1'
    sent: list[tuple[str, str]] = []
    project_root = tmp_path / 'repo-opencode'
    _write(project_root / '.ccb' / 'ccb.config', _single_agent_config_text('demo', 'opencode'))

    class FakeBackend:
        def send_text(self, pane_id: str, text: str) -> None:
            sent.append((pane_id, text))

        def is_alive(self, pane_id: str) -> bool:
            return pane_id == '%4'

    class FakeSession:
        data = {}
        opencode_project_id = 'proj-demo'
        opencode_session_id_filter = 'ses-demo'
        work_dir = str(project_root)

        def ensure_pane(self):
            return True, '%4'

    class FakeReader:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

        def capture_state(self):
            return {'session_path': str(tmp_path / 'opencode-session.json'), 'session_id': 'ses-demo'}

        def try_get_message(self, state):
            return (
                'legacy final',
                {
                    **state,
                    'last_assistant_id': 'msg-final',
                    'last_assistant_parent_id': 'msg-user',
                    'last_assistant_req_id': fixed_req_id,
                    'last_assistant_completed': 1234,
                },
            )

    monkeypatch.setattr(opencode_adapter_module, 'load_project_session', lambda work_dir, instance=None: FakeSession())
    monkeypatch.setattr(opencode_adapter_module, 'get_backend_for_session', lambda data: FakeBackend())
    monkeypatch.setattr(opencode_adapter_module, 'OpenCodeLogReader', FakeReader)

    app = CcbdApp(project_root)
    _freeze_next_job_id(app, monkeypatch, fixed_req_id)
    app.paths.workspace_path('demo').mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    client.attach(
        agent_name='demo',
        workspace_path=str(app.paths.workspace_path('demo')),
        backend_type='pane-backed',
        runtime_ref='tmux:%4',
        session_ref='ses-demo',
    )

    submit = client.submit(
        MessageEnvelope(
            project_id=app.project_id,
            to_agent='demo',
            from_actor='user',
            body='hello opencode',
            task_id='task-opencode',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']

    completed = _wait_for_job_status(client, job_id, 'completed', timeout=3.0)
    assert completed['reply'] == 'legacy final'
    assert completed['completion_reason'] == 'assistant_completed'
    assert completed['completion_confidence'] == 'observed'
    assert sent and sent[0][0] == '%4'
    assert fixed_req_id in sent[0][1]

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_opencode_pane_dead_becomes_failed_degraded(monkeypatch, tmp_path: Path) -> None:
    from provider_execution import opencode as opencode_adapter_module

    fixed_req_id = 'job_opencodedead'
    project_root = tmp_path / 'repo-opencode-dead'
    _write(project_root / '.ccb' / 'ccb.config', _single_agent_config_text('demo', 'opencode'))

    class DeadBackend:
        def send_text(self, pane_id: str, text: str) -> None:
            del pane_id, text

        def is_alive(self, pane_id: str) -> bool:
            del pane_id
            return False

    class FakeSession:
        data = {}
        opencode_project_id = 'proj-demo'
        opencode_session_id_filter = 'ses-demo'
        work_dir = str(project_root)

        def ensure_pane(self):
            return True, '%4'

    class EmptyReader:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

        def capture_state(self):
            return {'session_path': str(tmp_path / 'opencode-session.json'), 'session_id': 'ses-demo'}

        def try_get_message(self, state):
            return None, state

    monkeypatch.setattr(opencode_adapter_module, 'load_project_session', lambda work_dir, instance=None: FakeSession())
    monkeypatch.setattr(opencode_adapter_module, 'get_backend_for_session', lambda data: DeadBackend())
    monkeypatch.setattr(opencode_adapter_module, 'OpenCodeLogReader', EmptyReader)

    app = CcbdApp(project_root)
    _freeze_next_job_id(app, monkeypatch, fixed_req_id)
    app.paths.workspace_path('demo').mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    client.attach(
        agent_name='demo',
        workspace_path=str(app.paths.workspace_path('demo')),
        backend_type='pane-backed',
        runtime_ref='tmux:%4',
        session_ref='ses-demo',
    )

    submit = client.submit(
        MessageEnvelope(
            project_id=app.project_id,
            to_agent='demo',
            from_actor='user',
            body='hello opencode dead',
            task_id='task-opencode-dead',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']

    failed = _wait_for_job_status(client, job_id, 'failed', timeout=3.0)
    assert failed['reply'] == ''
    assert failed['completion_reason'] == 'pane_dead'
    assert failed['completion_confidence'] == 'degraded'

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_droid_legacy_completion_via_tracker(monkeypatch, tmp_path: Path) -> None:
    from provider_execution import droid as droid_adapter_module

    fixed_req_id = 'job_droid1'
    sent: list[tuple[str, str]] = []
    project_root = tmp_path / 'repo-droid'
    _write(project_root / '.ccb' / 'ccb.config', _single_agent_config_text('demo', 'droid'))

    class FakeBackend:
        def send_text(self, pane_id: str, text: str) -> None:
            sent.append((pane_id, text))

        def is_alive(self, pane_id: str) -> bool:
            return pane_id == '%5'

    class FakeSession:
        data = {}
        droid_session_path = str(tmp_path / 'droid-session.jsonl')
        droid_session_id = 'droid-session-id'
        work_dir = str(project_root)

        def ensure_pane(self):
            return True, '%5'

    class FakeReader:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs
            self._events = [
                ('user', f'CCB_REQ_ID: {fixed_req_id}\n\nprompt'),
                ('assistant', 'partial'),
                ('assistant', f'final\nCCB_DONE: {fixed_req_id}'),
            ]

        def set_preferred_session(self, session_path) -> None:
            del session_path

        def set_session_id_hint(self, session_id) -> None:
            del session_id

        def capture_state(self):
            return {'session_path': str(tmp_path / 'droid-session.jsonl'), 'offset': 0}

        def try_get_events(self, state):
            index = int(state.get('index', 0))
            if index >= len(self._events):
                return [], state
            return [self._events[index]], {**state, 'index': index + 1}

    monkeypatch.setattr(droid_adapter_module, 'load_project_session', lambda work_dir, instance=None: FakeSession())
    monkeypatch.setattr(droid_adapter_module, 'get_backend_for_session', lambda data: FakeBackend())
    monkeypatch.setattr(droid_adapter_module, 'DroidLogReader', FakeReader)

    app = CcbdApp(project_root)
    _freeze_next_job_id(app, monkeypatch, fixed_req_id)
    app.paths.workspace_path('demo').mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    client.attach(
        agent_name='demo',
        workspace_path=str(app.paths.workspace_path('demo')),
        backend_type='pane-backed',
        runtime_ref='tmux:%5',
        session_ref='droid-session-id',
    )

    submit = client.submit(
        MessageEnvelope(
            project_id=app.project_id,
            to_agent='demo',
            from_actor='user',
            body='hello droid',
            task_id='task-droid',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']

    completed = _wait_for_job_status(client, job_id, 'completed', timeout=3.0)
    assert completed['reply'] == 'partial\nfinal'
    assert completed['completion_reason'] == 'terminal_done_marker'
    assert completed['completion_confidence'] == 'degraded'
    assert sent and sent[0][0] == '%5'
    assert fixed_req_id in sent[0][1]

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_ccbd_socket_droid_pane_dead_becomes_failed_degraded(monkeypatch, tmp_path: Path) -> None:
    from provider_execution import droid as droid_adapter_module

    fixed_req_id = 'job_droiddead'
    project_root = tmp_path / 'repo-droid-dead'
    _write(project_root / '.ccb' / 'ccb.config', _single_agent_config_text('demo', 'droid'))

    class DeadBackend:
        def send_text(self, pane_id: str, text: str) -> None:
            del pane_id, text

        def is_alive(self, pane_id: str) -> bool:
            del pane_id
            return False

    class FakeSession:
        data = {}
        droid_session_path = str(tmp_path / 'droid-session.jsonl')
        droid_session_id = 'droid-session-id'
        work_dir = str(project_root)

        def ensure_pane(self):
            return True, '%5'

    class EmptyReader:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

        def set_preferred_session(self, session_path) -> None:
            del session_path

        def set_session_id_hint(self, session_id) -> None:
            del session_id

        def capture_state(self):
            return {'session_path': str(tmp_path / 'droid-session.jsonl'), 'offset': 0}

        def try_get_events(self, state):
            return [], state

    monkeypatch.setattr(droid_adapter_module, 'load_project_session', lambda work_dir, instance=None: FakeSession())
    monkeypatch.setattr(droid_adapter_module, 'get_backend_for_session', lambda data: DeadBackend())
    monkeypatch.setattr(droid_adapter_module, 'DroidLogReader', EmptyReader)

    app = CcbdApp(project_root)
    _freeze_next_job_id(app, monkeypatch, fixed_req_id)
    app.paths.workspace_path('demo').mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=app.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    _wait_for(app.paths.ccbd_socket_path)

    client = CcbdClient(app.paths.ccbd_socket_path)
    client.attach(
        agent_name='demo',
        workspace_path=str(app.paths.workspace_path('demo')),
        backend_type='pane-backed',
        runtime_ref='tmux:%5',
        session_ref='droid-session-id',
    )

    submit = client.submit(
        MessageEnvelope(
            project_id=app.project_id,
            to_agent='demo',
            from_actor='user',
            body='hello droid dead',
            task_id='task-droid-dead',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    job_id = submit['job_id']

    failed = _wait_for_job_status(client, job_id, 'failed', timeout=3.0)
    assert failed['reply'] == ''
    assert failed['completion_reason'] == 'pane_dead'
    assert failed['completion_confidence'] == 'degraded'

    shutdown = client.shutdown()
    assert shutdown['state'] == 'unmounted'
    thread.join(timeout=2)
    assert not thread.is_alive()
