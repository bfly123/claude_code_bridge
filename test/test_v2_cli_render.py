from __future__ import annotations

from types import SimpleNamespace

from cli.render import (
    render_ack,
    render_ask,
    render_doctor,
    render_doctor_bundle,
    render_fault_arm,
    render_fault_clear,
    render_fault_list,
    render_inbox,
    render_kill,
    render_logs,
    render_ps,
    render_queue,
    render_resubmit,
    render_retry,
    render_start,
    render_trace,
    render_wait,
    render_watch_batch,
)


def test_render_ask_includes_submission_and_jobs() -> None:
    summary = SimpleNamespace(
        project_id='proj-1',
        submission_id='sub-1',
        jobs=(
            {'job_id': 'job-1', 'agent_name': 'agent1', 'status': 'accepted'},
            {'job_id': 'job-2', 'agent_name': 'agent2', 'status': 'accepted'},
        ),
    )

    assert render_ask(summary) == (
        'accepted jobs=job-1@agent1,job-2@agent2',
        '[CCB_ASYNC_SUBMITTED jobs=job-1@agent1,job-2@agent2]',
    )


def test_render_resubmit_includes_origin_and_new_message_ids() -> None:
    summary = SimpleNamespace(
        project_id='proj-1',
        original_message_id='msg_old',
        message_id='msg_new',
        submission_id=None,
        jobs=(
            {'job_id': 'job-1', 'agent_name': 'agent1', 'status': 'accepted'},
        ),
    )

    assert render_resubmit(summary) == (
        'resubmit_status: accepted',
        'project_id: proj-1',
        'original_message_id: msg_old',
        'message_id: msg_new',
        'submission_id: None',
        'job: job-1 agent1 accepted',
    )


def test_render_retry_includes_attempt_lineage() -> None:
    summary = SimpleNamespace(
        project_id='proj-1',
        target='att_old',
        message_id='msg_1',
        original_attempt_id='att_old',
        attempt_id='att_new',
        job_id='job_new',
        agent_name='agent1',
        status='queued',
    )

    assert render_retry(summary) == (
        'retry_status: accepted',
        'project_id: proj-1',
        'target: att_old',
        'message_id: msg_1',
        'original_attempt_id: att_old',
        'attempt_id: att_new',
        'job_id: job_new',
        'agent_name: agent1',
        'status: queued',
    )


def test_render_fault_commands() -> None:
    list_summary = SimpleNamespace(
        project_id='proj-1',
        rule_count=1,
        rules=(
            SimpleNamespace(
                rule_id='flt_1',
                agent_name='agent2',
                task_id='drill-1',
                reason='api_error',
                remaining_count=2,
                created_at='2026-03-31T00:00:00Z',
                updated_at='2026-03-31T00:00:00Z',
                error_message='fault injection drill',
            ),
        ),
    )
    arm_summary = SimpleNamespace(
        project_id='proj-1',
        rule_id='flt_1',
        agent_name='agent2',
        task_id='drill-1',
        reason='api_error',
        remaining_count=2,
        error_message='fault injection drill',
    )
    clear_summary = SimpleNamespace(
        project_id='proj-1',
        target='all',
        cleared_count=1,
        cleared_rule_ids=('flt_1',),
    )

    assert render_fault_list(list_summary) == (
        'fault_status: ok',
        'project_id: proj-1',
        'rule_count: 1',
        'fault_rule: id=flt_1 agent=agent2 task=drill-1 reason=api_error remaining=2 created=2026-03-31T00:00:00Z updated=2026-03-31T00:00:00Z error=fault injection drill',
    )
    assert render_fault_arm(arm_summary) == (
        'fault_status: armed',
        'project_id: proj-1',
        'rule_id: flt_1',
        'agent_name: agent2',
        'task_id: drill-1',
        'reason: api_error',
        'remaining_count: 2',
        'error_message: fault injection drill',
    )
    assert render_fault_clear(clear_summary) == (
        'fault_status: cleared',
        'project_id: proj-1',
        'target: all',
        'cleared_count: 1',
        'cleared_rule_id: flt_1',
    )


def test_render_wait_includes_reply_details() -> None:
    summary = SimpleNamespace(
        wait_status='satisfied',
        project_id='proj-1',
        mode='all',
        target='msg_1',
        resolved_kind='message',
        expected_count=2,
        received_count=2,
        terminal_count=2,
        notice_count=0,
        waited_s=0.125,
        replies=(
            {
                'reply_id': 'rep_1',
                'message_id': 'msg_1',
                'attempt_id': 'att_1',
                'agent_name': 'codex',
                'job_id': 'job_1',
                'terminal_status': 'completed',
                'notice': False,
                'notice_kind': None,
                'reason': 'task_complete',
                'finished_at': '2026-03-30T00:00:10Z',
                'reply': 'done',
            },
        ),
    )

    assert render_wait(summary) == (
        'wait_status: satisfied',
        'project_id: proj-1',
        'mode: all',
        'target: msg_1',
        'resolved_kind: message',
        'expected_count: 2',
        'received_count: 2',
        'terminal_count: 2',
        'notice_count: 0',
        'waited_s: 0.125',
        'reply: id=rep_1 message=msg_1 attempt=att_1 agent=codex job=job_1 terminal=completed notice=false kind=None finished=2026-03-30T00:00:10Z reason=task_complete',
        'reply_text: done',
    )


def test_render_wait_notice_includes_heartbeat_fields() -> None:
    summary = SimpleNamespace(
        wait_status='notice',
        project_id='proj-1',
        mode='any',
        target='msg_1',
        resolved_kind='message',
        expected_count=1,
        received_count=1,
        terminal_count=0,
        notice_count=1,
        waited_s=0.125,
        replies=(
            {
                'reply_id': 'rep_heartbeat',
                'message_id': 'msg_1',
                'attempt_id': 'att_1',
                'agent_name': 'codex',
                'job_id': 'job_1',
                'terminal_status': 'incomplete',
                'notice': True,
                'notice_kind': 'heartbeat',
                'last_progress_at': '2026-03-30T00:00:00Z',
                'heartbeat_silence_seconds': 600.0,
                'reason': None,
                'finished_at': '2026-03-30T00:10:00Z',
                'reply': 'task still running',
            },
        ),
    )

    assert render_wait(summary) == (
        'wait_status: notice',
        'project_id: proj-1',
        'mode: any',
        'target: msg_1',
        'resolved_kind: message',
        'expected_count: 1',
        'received_count: 1',
        'terminal_count: 0',
        'notice_count: 1',
        'waited_s: 0.125',
        'reply: id=rep_heartbeat message=msg_1 attempt=att_1 agent=codex job=job_1 terminal=incomplete notice=true kind=heartbeat finished=2026-03-30T00:10:00Z reason=None',
        'reply_last_progress_at: 2026-03-30T00:00:00Z',
        'reply_heartbeat_silence_seconds: 600.0',
        'reply_text: task still running',
    )


def test_render_queue_includes_runtime_health_fields() -> None:
    payload = {
        'target': 'codex',
        'agent': {
            'agent_name': 'codex',
            'mailbox_id': 'mbx_codex',
            'mailbox_state': 'blocked',
            'runtime_state': 'degraded',
            'runtime_health': 'pane-dead',
            'lease_version': 2,
            'queue_depth': 1,
            'pending_reply_count': 0,
            'active_inbound_event_id': None,
            'last_inbound_started_at': None,
            'last_inbound_finished_at': None,
            'queued_events': (),
        },
    }

    assert render_queue(payload) == (
        'queue_status: ok',
        'target: codex',
        'agent_name: codex',
        'mailbox_id: mbx_codex',
        'mailbox_state: blocked',
        'runtime_state: degraded',
        'runtime_health: pane-dead',
        'lease_version: 2',
        'queue_depth: 1',
        'pending_reply_count: 0',
        'active_inbound_event_id: None',
        'last_inbound_started_at: None',
        'last_inbound_finished_at: None',
    )


def test_render_watch_batch_emits_terminal_footer() -> None:
    batch = SimpleNamespace(
        events=(
            {
                'event_id': 'evt-1',
                'job_id': 'job-1',
                'agent_name': 'agent1',
                'type': 'job_started',
                'timestamp': '2026-03-18T00:00:00Z',
            },
        ),
        terminal=True,
        job_id='job-1',
        agent_name='agent1',
        status='completed',
        reply='CCB_REQ_ID: job-1\n\ndone',
    )

    assert render_watch_batch(batch) == (
        'event: evt-1 job-1 agent1 job_started 2026-03-18T00:00:00Z',
        'watch_status: terminal',
        'job_id: job-1',
        'agent_name: agent1',
        'target_name: agent1',
        'status: completed',
        'reply: done',
    )


def test_render_ask_and_watch_batch_use_target_name_when_present() -> None:
    summary = SimpleNamespace(
        project_id='proj-1',
        submission_id=None,
        jobs=(
            {'job_id': 'job-1', 'agent_name': 'reviewer', 'target_name': 'reviewer', 'status': 'accepted'},
        ),
    )
    batch = SimpleNamespace(
        events=(
            {
                'event_id': 'evt-1',
                'job_id': 'job-1',
                'agent_name': 'reviewer',
                'target_name': 'reviewer',
                'type': 'job_started',
                'timestamp': '2026-03-18T00:00:00Z',
            },
        ),
        terminal=True,
        job_id='job-1',
        agent_name='reviewer',
        target_name='reviewer',
        status='completed',
        reply='done',
    )

    assert render_ask(summary) == (
        'accepted job=job-1 target=reviewer',
        '[CCB_ASYNC_SUBMITTED job=job-1 target=reviewer]',
    )
    assert render_watch_batch(batch) == (
        'event: evt-1 job-1 reviewer job_started 2026-03-18T00:00:00Z',
        'watch_status: terminal',
        'job_id: job-1',
        'agent_name: reviewer',
        'target_name: reviewer',
        'status: completed',
        'reply: done',
    )


def test_render_ps_and_doctor_keep_expected_line_shapes() -> None:
    ps_payload = {
        'project_id': 'proj-1',
        'ccbd_state': 'mounted',
        'agents': [
            {
                'agent_name': 'codex',
                'provider': 'codex',
                'state': 'idle',
                'queue_depth': 0,
                'binding_status': 'ready',
                'runtime_ref': 'tmux:%1',
                'session_ref': '/tmp/.codex-session',
                'session_file': '/tmp/.codex-session',
                'session_id': 'codex-session',
                'binding_source': 'provider-session',
                'workspace_path': '/tmp/ws/codex',
                'terminal': 'tmux',
                'runtime_pid': 4321,
                'runtime_root': '/tmp/runtime-root',
                'job_id': 'job-object-1',
                'job_owner_pid': 654,
                'tmux_socket_name': 'sock-a',
                'tmux_socket_path': None,
                'pane_id': '%1',
                'active_pane_id': '%1',
                'pane_title_marker': 'CCB-codex',
                'pane_state': 'alive',
            }
        ],
    }
    doctor_payload = {
        'project': '/tmp/repo',
        'project_id': 'proj-1',
        'installation': {
            'path': '/tmp/install',
            'install_mode': 'release',
            'source_kind': 'release',
            'version': '5.2.8',
            'channel': 'stable',
            'build_time': '2026-04-09T10:11:12Z',
            'platform': 'linux',
            'arch': 'x86_64',
        },
        'requirements': {
            'python_executable': '/usr/bin/python3',
            'python_version': '3.11.0',
            'tmux_available': True,
            'tmux_path': '/usr/bin/tmux',
            'provider_commands': (
                {
                    'provider': 'codex',
                    'executable': 'codex',
                    'available': True,
                    'path': '/usr/bin/codex',
                },
            ),
        },
        'ccbd': {
            'state': 'mounted',
            'health': 'healthy',
            'generation': 1,
            'ipc_kind': 'named_pipe',
            'ipc_ref': r'\\.\pipe\ccb-proj-1-ccbd',
            'ipc_state': 'mounted',
            'ipc_updated_at': '2026-04-03T00:05:00Z',
            'backend_family': 'tmux',
            'backend_impl': 'psmux',
            'last_heartbeat_at': '2026-03-18T00:00:00Z',
            'pid_alive': True,
            'socket_connectable': True,
            'heartbeat_fresh': True,
            'takeover_allowed': False,
            'reason': 'healthy',
            'active_execution_count': 0,
            'recoverable_execution_count': 0,
            'nonrecoverable_execution_count': 0,
            'pending_items_count': 0,
            'terminal_pending_count': 0,
            'recoverable_execution_providers': ['codex'],
            'nonrecoverable_execution_providers': [],
            'last_restore_at': None,
            'last_restore_running_job_count': 0,
            'last_restore_restored_execution_count': 0,
            'last_restore_replay_pending_count': 0,
            'last_restore_terminal_pending_count': 0,
            'last_restore_abandoned_execution_count': 0,
            'last_restore_already_active_count': 0,
            'last_restore_results_text': '',
            'namespace_epoch': 4,
            'namespace_backend_ref': r'\\.\pipe\psmux-repo',
            'namespace_session_name': 'ccb-repo',
            'namespace_workspace_name': 'ccb',
            'namespace_tmux_socket_path': '/tmp/repo/.ccb/ccbd/tmux.sock',
            'namespace_tmux_session_name': 'ccb-repo',
            'namespace_layout_version': 1,
            'namespace_ui_attachable': True,
            'namespace_last_started_at': '2026-04-03T00:05:00Z',
            'namespace_last_destroyed_at': None,
            'namespace_last_destroy_reason': None,
            'namespace_backend_family': 'tmux',
            'namespace_backend_impl': 'psmux',
            'namespace_last_event_kind': 'namespace_created',
            'namespace_last_event_at': '2026-04-03T00:05:00Z',
            'namespace_last_event_epoch': 4,
            'namespace_last_event_backend_ref': r'\\.\pipe\psmux-repo',
            'namespace_last_event_socket_path': '/tmp/repo/.ccb/ccbd/tmux.sock',
            'namespace_last_event_session_name': 'ccb-repo',
        },
        'agents': [
            {
                'agent_name': 'codex',
                'provider': 'codex',
                'health': 'healthy',
                'completion_family': 'protocol_turn',
                'binding_status': 'ready',
                'runtime_ref': 'tmux:%1',
                'session_ref': '/tmp/.codex-session',
                'session_file': '/tmp/.codex-session',
                'session_id': 'codex-session',
                'binding_source': 'external-attach',
                'workspace_path': '/tmp/ws/codex',
                'terminal': 'tmux',
                'runtime_pid': 4321,
                'runtime_root': '/tmp/runtime-root',
                'job_id': 'job-object-1',
                'job_owner_pid': 654,
                'tmux_socket_name': 'sock-a',
                'tmux_socket_path': None,
                'pane_id': '%1',
                'active_pane_id': '%1',
                'pane_title_marker': 'CCB-codex',
                'pane_state': 'alive',
                'execution_resume_supported': True,
                'execution_restore_mode': 'provider_resume',
                'execution_restore_reason': None,
                'execution_restore_detail': 'resume ok',
            }
        ],
    }

    ps_lines = render_ps(ps_payload)
    doctor_lines = render_doctor(doctor_payload)

    assert ps_lines[0] == 'project_id: proj-1'
    assert ps_lines[2] == 'agent: name=codex state=idle provider=codex queue=0'
    assert ps_lines[3] == (
        'binding: status=ready runtime=tmux:%1 session=/tmp/.codex-session '
        'session_file=/tmp/.codex-session session_id=codex-session '
        'source=provider-session workspace=/tmp/ws/codex terminal=tmux '
        'runtime_pid=4321 runtime_root=/tmp/runtime-root job=job-object-1 job_owner=654 '
        'socket=sock-a socket_path=None pane=%1 active_pane=%1 pane_state=alive marker=CCB-codex'
    )

    assert doctor_lines[0] == 'project: /tmp/repo'
    assert 'install_mode: release' in doctor_lines
    assert 'install_channel: stable' in doctor_lines
    assert 'requirement_tmux_available: True' in doctor_lines
    assert 'requirement_provider: name=codex executable=codex available=True path=/usr/bin/codex' in doctor_lines
    assert 'ccbd_state: mounted' in doctor_lines
    assert r'ccbd_ipc_ref: \\.\pipe\ccb-proj-1-ccbd' in doctor_lines
    assert 'ccbd_ipc_state: mounted' in doctor_lines
    assert 'ccbd_backend_impl: psmux' in doctor_lines
    assert r'ccbd_namespace_backend_ref: \\.\pipe\psmux-repo' in doctor_lines
    assert 'ccbd_namespace_session_name: ccb-repo' in doctor_lines
    assert 'ccbd_namespace_workspace_name: ccb' in doctor_lines
    assert 'ccbd_namespace_tmux_session_name: ccb-repo' in doctor_lines
    assert 'ccbd_namespace_backend_impl: psmux' in doctor_lines
    assert r'ccbd_namespace_last_event_backend_ref: \\.\pipe\psmux-repo' in doctor_lines
    assert 'agent: name=codex health=healthy provider=codex completion=protocol_turn' in doctor_lines
    assert (
        'binding: status=ready runtime=tmux:%1 session=/tmp/.codex-session '
        'session_file=/tmp/.codex-session session_id=codex-session '
        'source=external-attach workspace=/tmp/ws/codex terminal=tmux '
        'runtime_pid=4321 runtime_root=/tmp/runtime-root job=job-object-1 job_owner=654 '
        'socket=sock-a socket_path=None pane=%1 active_pane=%1 pane_state=alive marker=CCB-codex'
    ) in doctor_lines
    assert 'restore: supported=True mode=provider_resume reason=None' in doctor_lines


def test_render_start_and_kill_include_tmux_cleanup_summary() -> None:
    cleanup = (
        SimpleNamespace(
            socket_name=None,
            owned_panes=('%1', '%2'),
            active_panes=('%1',),
            orphaned_panes=('%2',),
            killed_panes=('%2',),
        ),
    )
    start = SimpleNamespace(
        project_root='/tmp/repo',
        project_id='proj-1',
        daemon_started=True,
        socket_path='/tmp/repo/.ccb/ccbd/ccbd.sock',
        started=('agent1', 'agent2'),
        cleanup_summaries=cleanup,
    )
    kill = SimpleNamespace(
        project_id='proj-1',
        state='unmounted',
        socket_path='/tmp/repo/.ccb/ccbd/ccbd.sock',
        forced=True,
        cleanup_summaries=cleanup,
    )

    start_lines = render_start(start)
    kill_lines = render_kill(kill)

    assert 'agents: agent1, agent2' in start_lines
    assert 'tmux_cleanup: socket=<default> owned=%1,%2 active=%1 orphaned=%2 killed=%2' in start_lines
    assert 'kill_status: ok' in kill_lines
    assert 'tmux_cleanup: socket=<default> owned=%1,%2 active=%1 orphaned=%2 killed=%2' in kill_lines


def test_render_logs_includes_tail_content() -> None:
    summary = SimpleNamespace(
        project_id='proj-1',
        agent_name='agent1',
        provider='codex',
        runtime_ref='tmux:%1',
        session_ref='/tmp/.codex-agent1-session',
        entries=(
            SimpleNamespace(
                source='runtime',
                path='/tmp/runtime.log',
                lines=('line 1', 'line 2'),
            ),
        ),
    )

    assert render_logs(summary) == (
        'logs_status: ok',
        'project_id: proj-1',
        'agent_name: agent1',
        'provider: codex',
        'runtime_ref: tmux:%1',
        'session_ref: /tmp/.codex-agent1-session',
        'log_count: 1',
        'log: runtime /tmp/runtime.log',
        'log_line: line 1',
        'log_line: line 2',
    )


def test_render_doctor_bundle_reports_output_location() -> None:
    summary = SimpleNamespace(
        project_root='/tmp/repo',
        project_id='proj-1',
        bundle_id='bundle-1',
        bundle_path='/tmp/repo/.ccb/ccbd/support/bundle-1.tar.gz',
        file_count=12,
        included_count=10,
        missing_count=1,
        truncated_count=2,
        doctor_error=None,
    )

    assert render_doctor_bundle(summary) == (
        'doctor_bundle_status: ok',
        'project: /tmp/repo',
        'project_id: proj-1',
        'bundle_id: bundle-1',
        'bundle_path: /tmp/repo/.ccb/ccbd/support/bundle-1.tar.gz',
        'file_count: 12',
        'included_count: 10',
        'missing_count: 1',
        'truncated_count: 2',
        'doctor_error: None',
    )


def test_render_trace_keeps_line_protocol_shape() -> None:
    payload = {
        'target': 'job_123',
        'resolved_kind': 'job',
        'submission_id': None,
        'message_id': 'msg_1',
        'attempt_id': 'att_1',
        'reply_id': None,
        'job_id': 'job_123',
        'message_count': 1,
        'attempt_count': 1,
        'reply_count': 1,
        'event_count': 2,
        'job_count': 1,
        'submission': None,
        'messages': [
            {
                'message_id': 'msg_1',
                'origin_message_id': None,
                'submission_id': None,
                'from_actor': 'claude',
                'target_scope': 'single',
                'target_agents': ['codex'],
                'message_class': 'task_request',
                'message_state': 'completed',
                'priority': 100,
                'created_at': '2026-03-30T00:00:00Z',
                'updated_at': '2026-03-30T00:00:10Z',
            }
        ],
        'attempts': [
            {
                'attempt_id': 'att_1',
                'message_id': 'msg_1',
                'agent_name': 'codex',
                'provider': 'codex',
                'job_id': 'job_123',
                'retry_index': 0,
                'attempt_state': 'completed',
                'started_at': '2026-03-30T00:00:01Z',
                'updated_at': '2026-03-30T00:00:10Z',
            }
        ],
        'replies': [
            {
                'reply_id': 'rep_1',
                'message_id': 'msg_1',
                'attempt_id': 'att_1',
                'agent_name': 'codex',
                'terminal_status': 'completed',
                'reply_size': 4,
                'notice': False,
                'notice_kind': None,
                'reason': 'task_complete',
                'finished_at': '2026-03-30T00:00:10Z',
                'reply_preview': 'done',
            }
        ],
        'events': [
            {
                'inbound_event_id': 'iev_1',
                'agent_name': 'codex',
                'event_type': 'task_request',
                'status': 'consumed',
                'mailbox_state': 'idle',
                'mailbox_active': False,
                'message_id': 'msg_1',
                'attempt_id': 'att_1',
                'created_at': '2026-03-30T00:00:00Z',
                'finished_at': '2026-03-30T00:00:10Z',
            },
            {
                'inbound_event_id': 'iev_2',
                'agent_name': 'claude',
                'event_type': 'task_reply',
                'status': 'queued',
                'mailbox_state': 'blocked',
                'mailbox_active': False,
                'message_id': 'msg_1',
                'attempt_id': 'att_1',
                'created_at': '2026-03-30T00:00:10Z',
                'finished_at': None,
            },
        ],
        'jobs': [
            {
                'job_id': 'job_123',
                'agent_name': 'codex',
                'provider': 'codex',
                'status': 'completed',
                'submission_id': None,
                'created_at': '2026-03-30T00:00:00Z',
                'updated_at': '2026-03-30T00:00:10Z',
            }
        ],
    }

    lines = render_trace(payload)

    assert lines[0] == 'trace_status: ok'
    assert 'resolved_kind: job' in lines
    assert 'message_count: 1' in lines
    assert 'attempt_count: 1' in lines
    assert 'reply_count: 1' in lines
    assert 'event_count: 2' in lines
    assert 'job_count: 1' in lines
    assert 'message: id=msg_1 submission=None origin=None from=claude scope=single targets=codex class=task_request state=completed priority=100 created=2026-03-30T00:00:00Z updated=2026-03-30T00:00:10Z' in lines
    assert 'attempt: id=att_1 message=msg_1 agent=codex provider=codex job=job_123 retry=0 state=completed started=2026-03-30T00:00:01Z updated=2026-03-30T00:00:10Z' in lines
    assert 'reply: id=rep_1 message=msg_1 attempt=att_1 agent=codex terminal=completed size=4 notice=false kind=None reason=task_complete finished=2026-03-30T00:00:10Z preview=done' in lines
    assert 'event: id=iev_1 agent=codex type=task_request status=consumed mailbox_state=idle active=false message=msg_1 attempt=att_1 created=2026-03-30T00:00:00Z finished=2026-03-30T00:00:10Z' in lines
    assert 'event: id=iev_2 agent=claude type=task_reply status=queued mailbox_state=blocked active=false message=msg_1 attempt=att_1 created=2026-03-30T00:00:10Z finished=None' in lines
    assert 'job: id=job_123 agent=codex provider=codex status=completed submission=None created=2026-03-30T00:00:00Z updated=2026-03-30T00:00:10Z' in lines


def test_render_inbox_and_ack_include_reply_delivery_details() -> None:
    inbox_payload = {
        'target': 'claude',
        'agent': {
            'agent_name': 'claude',
            'mailbox_id': 'mbx_claude',
            'mailbox_state': 'blocked',
            'lease_version': 0,
            'queue_depth': 2,
            'pending_reply_count': 2,
            'active_inbound_event_id': None,
        },
        'item_count': 2,
        'head': {
            'inbound_event_id': 'iev_2',
            'event_type': 'task_reply',
            'status': 'queued',
            'reply_id': 'rep_1',
            'source_actor': 'codex',
            'reply_terminal_status': 'completed',
            'reply_notice': False,
            'reply_notice_kind': None,
            'job_id': 'job_123',
            'reply_finished_at': '2026-03-30T00:00:10Z',
            'reply': 'CCB_REQ_ID: job_123\n\ndone',
        },
        'items': (
            {
                'position': 1,
                'inbound_event_id': 'iev_2',
                'event_type': 'task_reply',
                'status': 'queued',
                'priority': 10,
                'message_id': 'msg_1',
                'attempt_id': 'att_1',
                'job_id': 'job_123',
                'source_actor': 'codex',
                'reply_id': 'rep_1',
                'reply_terminal_status': 'completed',
                'reply_notice': False,
                'reply_notice_kind': None,
                'reply_preview': 'done',
            },
            {
                'position': 2,
                'inbound_event_id': 'iev_3',
                'event_type': 'task_reply',
                'status': 'queued',
                'priority': 10,
                'message_id': 'msg_2',
                'attempt_id': 'att_2',
                'job_id': 'job_124',
                'source_actor': 'codex',
                'reply_id': 'rep_2',
                'reply_terminal_status': 'completed',
                'reply_notice': True,
                'reply_notice_kind': 'heartbeat',
                'reply_preview': 'next',
            },
        ),
    }

    inbox_lines = render_inbox(inbox_payload)

    assert inbox_lines[0] == 'inbox_status: ok'
    assert 'head_reply_id: rep_1' in inbox_lines
    assert 'head_reply_notice: false' in inbox_lines
    assert 'head_reply_job_id: job_123' in inbox_lines
    assert 'reply: done' in inbox_lines
    assert 'inbox_item: pos=1 event=iev_2 type=task_reply status=queued priority=10 message=msg_1 attempt=att_1 job=job_123 from=codex reply=rep_1 terminal=completed notice=false kind=None control_job=job_123 preview=done' in inbox_lines

    ack_payload = {
        'target': 'claude',
        'agent_name': 'claude',
        'acknowledged_inbound_event_id': 'iev_2',
        'message_id': 'msg_1',
        'attempt_id': 'att_1',
        'job_id': 'job_123',
        'reply_id': 'rep_1',
        'reply_from_agent': 'codex',
        'reply_terminal_status': 'completed',
        'reply_notice': False,
        'reply_notice_kind': None,
        'reply_finished_at': '2026-03-30T00:00:10Z',
        'next_inbound_event_id': 'iev_3',
        'next_event_type': 'task_reply',
        'mailbox': {
            'mailbox_state': 'blocked',
            'queue_depth': 1,
            'pending_reply_count': 1,
        },
        'reply': 'CCB_REQ_ID: job_123\n\ndone',
    }

    ack_lines = render_ack(ack_payload)

    assert ack_lines[0] == 'ack_status: ok'
    assert 'acknowledged_inbound_event_id: iev_2' in ack_lines
    assert 'job_id: job_123' in ack_lines
    assert 'reply_notice: false' in ack_lines
    assert 'next_inbound_event_id: iev_3' in ack_lines
    assert ack_lines[-1] == 'reply: done'
