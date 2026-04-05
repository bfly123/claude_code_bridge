from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import re


_PROTOCOL_LINE_RE = re.compile(r'^\s*CCB_(?:REQ_ID|BEGIN|DONE):.*$', re.MULTILINE)


def _display_text(value: object) -> str:
    text = str(value or '')
    if not text:
        return ''
    text = _PROTOCOL_LINE_RE.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def render_config_validate(summary) -> tuple[str, ...]:
    return (
        'config_status: valid',
        f'project: {summary.project_root}',
        f'project_id: {summary.project_id}',
        f'config_source: {summary.source or "<default>"}',
        f'used_default: {str(summary.used_default).lower()}',
        f'default_agents: {", ".join(summary.default_agents)}',
        f'agents: {", ".join(summary.agent_names)}',
        f'cmd_enabled: {str(summary.cmd_enabled).lower()}',
        f'layout: {summary.layout_spec}',
    )


def render_start(summary) -> tuple[str, ...]:
    lines = [
        'start_status: ok',
        f'project: {summary.project_root}',
        f'project_id: {summary.project_id}',
        f'ccbd_started: {str(summary.daemon_started).lower()}',
        f'socket_path: {summary.socket_path}',
        f'agents: {", ".join(summary.started)}',
    ]
    lines.extend(_render_tmux_cleanup_summaries(getattr(summary, 'cleanup_summaries', ()) or ()))
    return tuple(lines)


def render_ask(summary) -> tuple[str, ...]:
    jobs = tuple(summary.jobs or ())
    if len(jobs) == 1:
        job = jobs[0]
        target = job.get('target_name') or job.get('agent_name')
        return (f'accepted job={job["job_id"]} target={target}',)
    rendered_jobs = ','.join(
        f'{job["job_id"]}@{job.get("target_name") or job.get("agent_name")}'
        for job in jobs
    )
    return (f'accepted jobs={rendered_jobs}',)


def render_resubmit(summary) -> tuple[str, ...]:
    lines = [
        'resubmit_status: accepted',
        f'project_id: {summary.project_id}',
        f'original_message_id: {summary.original_message_id}',
        f'message_id: {summary.message_id}',
        f'submission_id: {summary.submission_id}',
    ]
    for job in summary.jobs:
        target = job.get('target_name') or job.get('agent_name')
        lines.append(f'job: {job["job_id"]} {target} {job["status"]}')
    return tuple(lines)


def render_retry(summary) -> tuple[str, ...]:
    lines = [
        'retry_status: accepted',
        f'project_id: {summary.project_id}',
        f'target: {summary.target}',
        f'message_id: {summary.message_id}',
        f'original_attempt_id: {summary.original_attempt_id}',
        f'attempt_id: {summary.attempt_id}',
        f'job_id: {summary.job_id}',
        f'agent_name: {summary.agent_name}',
        f'status: {summary.status}',
    ]
    return tuple(lines)


def render_wait(summary) -> tuple[str, ...]:
    lines = [
        f'wait_status: {getattr(summary, "wait_status", "satisfied")}',
        f'project_id: {summary.project_id}',
        f'mode: {summary.mode}',
        f'target: {summary.target}',
        f'resolved_kind: {summary.resolved_kind}',
        f'expected_count: {summary.expected_count}',
        f'received_count: {summary.received_count}',
        f'terminal_count: {getattr(summary, "terminal_count", summary.received_count)}',
        f'notice_count: {getattr(summary, "notice_count", 0)}',
        f'waited_s: {summary.waited_s:.3f}',
    ]
    for reply in summary.replies:
        lines.append(
            'reply: '
            f'id={reply["reply_id"]} message={reply["message_id"]} attempt={reply["attempt_id"]} '
            f'agent={reply["agent_name"]} job={reply.get("job_id")} terminal={reply["terminal_status"]} '
            f'notice={str(bool(reply.get("notice"))).lower()} kind={reply.get("notice_kind")} '
            f'finished={reply["finished_at"]} reason={reply.get("reason")}'
        )
        if reply.get('last_progress_at') is not None:
            lines.append(f'reply_last_progress_at: {reply.get("last_progress_at")}')
        if reply.get('heartbeat_silence_seconds') is not None:
            lines.append(f'reply_heartbeat_silence_seconds: {reply.get("heartbeat_silence_seconds")}')
        lines.append(f'reply_text: {_display_text(reply.get("reply"))}')
    return tuple(lines)


def render_mapping(payload: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(f'{key}: {value}' for key, value in payload.items())


def render_job_state(payload: Mapping[str, object]) -> tuple[str, ...]:
    keys = (
        'job_id',
        'agent_name',
        'target_kind',
        'target_name',
        'provider',
        'provider_instance',
        'status',
        'reply',
        'completion_reason',
        'completion_confidence',
        'updated_at',
    )
    lines: list[str] = []
    for key in keys:
        value = payload.get(key)
        if key == 'reply':
            value = _display_text(value)
        lines.append(f'{key}: {value}')
    return tuple(lines)


def render_pend(payload: Mapping[str, object]) -> tuple[str, ...]:
    lines = list(render_job_state(payload))
    if payload.get('mailbox_reply_ready') is not None:
        lines.extend(
            [
                f'mailbox_reply_ready: {str(bool(payload.get("mailbox_reply_ready"))).lower()}',
                f'mailbox_reply_id: {payload.get("mailbox_reply_id")}',
                f'mailbox_reply_from_agent: {payload.get("mailbox_reply_from_agent")}',
                f'mailbox_reply_terminal_status: {payload.get("mailbox_reply_terminal_status")}',
                f'mailbox_reply_notice: {str(bool(payload.get("mailbox_reply_notice"))).lower()}',
                f'mailbox_reply_notice_kind: {payload.get("mailbox_reply_notice_kind")}',
                f'mailbox_reply_job_id: {payload.get("mailbox_reply_job_id")}',
                f'mailbox_reply_finished_at: {payload.get("mailbox_reply_finished_at")}',
            ]
        )
        if payload.get('mailbox_reply_last_progress_at') is not None:
            lines.append(f'mailbox_reply_last_progress_at: {payload.get("mailbox_reply_last_progress_at")}')
        if payload.get('mailbox_reply_heartbeat_silence_seconds') is not None:
            lines.append(
                f'mailbox_reply_heartbeat_silence_seconds: {payload.get("mailbox_reply_heartbeat_silence_seconds")}'
            )
        if payload.get('mailbox_reply') is not None:
            lines.append(f'mailbox_reply: {_display_text(payload.get("mailbox_reply"))}')
    return tuple(lines)


def render_queue(payload: Mapping[str, object]) -> tuple[str, ...]:
    lines: list[str] = [
        'queue_status: ok',
        f'target: {payload.get("target")}',
    ]
    if payload.get('target') == 'all':
        lines.extend(
            [
                f'agent_count: {payload.get("agent_count")}',
                f'queued_agent_count: {payload.get("queued_agent_count")}',
                f'active_agent_count: {payload.get("active_agent_count")}',
                f'total_queue_depth: {payload.get("total_queue_depth")}',
                f'total_pending_reply_count: {payload.get("total_pending_reply_count")}',
            ]
        )
        agents = payload.get('agents') or ()
        for agent in agents:
            lines.append(
                'queue_agent: '
                f'name={agent["agent_name"]} runtime_state={agent.get("runtime_state")} '
                f'runtime_health={agent.get("runtime_health")} state={agent["mailbox_state"]} '
                f'depth={agent["queue_depth"]} pending_replies={agent["pending_reply_count"]}'
            )
        return tuple(lines)

    agent = payload.get('agent') or {}
    lines.extend(
        [
            f'agent_name: {agent.get("agent_name")}',
            f'mailbox_id: {agent.get("mailbox_id")}',
            f'mailbox_state: {agent.get("mailbox_state")}',
            f'runtime_state: {agent.get("runtime_state")}',
            f'runtime_health: {agent.get("runtime_health")}',
            f'lease_version: {agent.get("lease_version")}',
            f'queue_depth: {agent.get("queue_depth")}',
            f'pending_reply_count: {agent.get("pending_reply_count")}',
            f'active_inbound_event_id: {agent.get("active_inbound_event_id")}',
            f'last_inbound_started_at: {agent.get("last_inbound_started_at")}',
            f'last_inbound_finished_at: {agent.get("last_inbound_finished_at")}',
        ]
    )
    active = agent.get('active')
    if isinstance(active, Mapping):
        lines.append(
            'queue_active: '
            f'event={active.get("inbound_event_id")} type={active.get("event_type")} status={active.get("status")} '
            f'message={active.get("message_id")} attempt={active.get("attempt_id")} job={active.get("job_id")}'
        )
    for event in agent.get('queued_events') or ():
        lines.append(
            'queue_event: '
            f'pos={event["position"]} event={event["inbound_event_id"]} type={event["event_type"]} '
            f'status={event["status"]} priority={event["priority"]} '
            f'message={event["message_id"]} attempt={event["attempt_id"]} job={event["job_id"]}'
        )
    return tuple(lines)


def render_trace(payload: Mapping[str, object]) -> tuple[str, ...]:
    lines: list[str] = [
        'trace_status: ok',
        f'target: {payload.get("target")}',
        f'resolved_kind: {payload.get("resolved_kind")}',
        f'submission_id: {payload.get("submission_id")}',
        f'message_id: {payload.get("message_id")}',
        f'attempt_id: {payload.get("attempt_id")}',
        f'reply_id: {payload.get("reply_id")}',
        f'job_id: {payload.get("job_id")}',
        f'message_count: {payload.get("message_count")}',
        f'attempt_count: {payload.get("attempt_count")}',
        f'reply_count: {payload.get("reply_count")}',
        f'event_count: {payload.get("event_count")}',
        f'job_count: {payload.get("job_count")}',
    ]
    submission = payload.get('submission')
    if isinstance(submission, Mapping):
        lines.append(
            'submission: '
            f'id={submission.get("submission_id")} from={submission.get("from_actor")} '
            f'scope={submission.get("target_scope")} task={submission.get("task_id")} '
            f'jobs={len(submission.get("job_ids") or [])} '
            f'created={submission.get("created_at")} updated={submission.get("updated_at")}'
        )
    for message in payload.get('messages') or ():
        targets = ','.join(message.get('target_agents') or [])
        lines.append(
            'message: '
            f'id={message.get("message_id")} submission={message.get("submission_id")} '
            f'origin={message.get("origin_message_id")} '
            f'from={message.get("from_actor")} scope={message.get("target_scope")} '
            f'targets={targets} class={message.get("message_class")} '
            f'state={message.get("message_state")} priority={message.get("priority")} '
            f'created={message.get("created_at")} updated={message.get("updated_at")}'
        )
    for attempt in payload.get('attempts') or ():
        lines.append(
            'attempt: '
            f'id={attempt.get("attempt_id")} message={attempt.get("message_id")} '
            f'agent={attempt.get("agent_name")} provider={attempt.get("provider")} '
            f'job={attempt.get("job_id")} retry={attempt.get("retry_index")} '
            f'state={attempt.get("attempt_state")} started={attempt.get("started_at")} '
            f'updated={attempt.get("updated_at")}'
        )
    for reply in payload.get('replies') or ():
        lines.append(
            'reply: '
            f'id={reply.get("reply_id")} message={reply.get("message_id")} '
            f'attempt={reply.get("attempt_id")} agent={reply.get("agent_name")} '
            f'terminal={reply.get("terminal_status")} size={reply.get("reply_size")} '
            f'notice={str(bool(reply.get("notice"))).lower()} kind={reply.get("notice_kind")} '
            f'reason={reply.get("reason")} finished={reply.get("finished_at")} '
            f'preview={reply.get("reply_preview")}'
        )
    for event in payload.get('events') or ():
        lines.append(
            'event: '
            f'id={event.get("inbound_event_id")} agent={event.get("agent_name")} '
            f'type={event.get("event_type")} status={event.get("status")} '
            f'mailbox_state={event.get("mailbox_state")} active={str(bool(event.get("mailbox_active"))).lower()} '
            f'message={event.get("message_id")} attempt={event.get("attempt_id")} '
            f'created={event.get("created_at")} finished={event.get("finished_at")}'
        )
    for job in payload.get('jobs') or ():
        lines.append(
            'job: '
            f'id={job.get("job_id")} agent={job.get("agent_name")} provider={job.get("provider")} '
            f'status={job.get("status")} submission={job.get("submission_id")} '
            f'created={job.get("created_at")} updated={job.get("updated_at")}'
        )
    return tuple(lines)


def render_inbox(payload: Mapping[str, object]) -> tuple[str, ...]:
    agent = payload.get('agent') or {}
    head = payload.get('head') or {}
    lines: list[str] = [
        'inbox_status: ok',
        f'target: {payload.get("target")}',
        f'agent_name: {agent.get("agent_name")}',
        f'mailbox_id: {agent.get("mailbox_id")}',
        f'mailbox_state: {agent.get("mailbox_state")}',
        f'lease_version: {agent.get("lease_version")}',
        f'queue_depth: {agent.get("queue_depth")}',
        f'pending_reply_count: {agent.get("pending_reply_count")}',
        f'active_inbound_event_id: {agent.get("active_inbound_event_id")}',
        f'item_count: {payload.get("item_count")}',
        f'head_inbound_event_id: {head.get("inbound_event_id")}',
        f'head_event_type: {head.get("event_type")}',
        f'head_status: {head.get("status")}',
    ]
    if head.get('reply_id') is not None:
        lines.extend(
            [
                f'head_reply_id: {head.get("reply_id")}',
                f'head_reply_from_agent: {head.get("source_actor")}',
                f'head_reply_terminal_status: {head.get("reply_terminal_status")}',
                f'head_reply_notice: {str(bool(head.get("reply_notice"))).lower()}',
                f'head_reply_notice_kind: {head.get("reply_notice_kind")}',
                f'head_reply_job_id: {head.get("job_id")}',
                f'head_reply_finished_at: {head.get("reply_finished_at")}',
            ]
        )
        if head.get('reply_last_progress_at') is not None:
            lines.append(f'head_reply_last_progress_at: {head.get("reply_last_progress_at")}')
        if head.get('reply_heartbeat_silence_seconds') is not None:
            lines.append(f'head_reply_heartbeat_silence_seconds: {head.get("reply_heartbeat_silence_seconds")}')
    if head.get('reply') is not None:
        lines.append(f'reply: {_display_text(head.get("reply"))}')
    for item in payload.get('items') or ():
        parts = [
            'inbox_item:',
            f'pos={item.get("position")}',
            f'event={item.get("inbound_event_id")}',
            f'type={item.get("event_type")}',
            f'status={item.get("status")}',
            f'priority={item.get("priority")}',
            f'message={item.get("message_id")}',
            f'attempt={item.get("attempt_id")}',
            f'job={item.get("job_id")}',
            f'from={item.get("source_actor")}',
        ]
        if item.get('reply_id') is not None:
            parts.extend(
                [
                    f'reply={item.get("reply_id")}',
                    f'terminal={item.get("reply_terminal_status")}',
                    f'notice={str(bool(item.get("reply_notice"))).lower()}',
                    f'kind={item.get("reply_notice_kind")}',
                    f'control_job={item.get("job_id")}',
                    f'preview={item.get("reply_preview")}',
                ]
            )
        lines.append(' '.join(parts))
    return tuple(lines)


def render_ack(payload: Mapping[str, object]) -> tuple[str, ...]:
    mailbox = payload.get('mailbox') or {}
    lines: list[str] = [
        'ack_status: ok',
        f'target: {payload.get("target")}',
        f'agent_name: {payload.get("agent_name")}',
        f'acknowledged_inbound_event_id: {payload.get("acknowledged_inbound_event_id")}',
        f'message_id: {payload.get("message_id")}',
        f'attempt_id: {payload.get("attempt_id")}',
        f'job_id: {payload.get("job_id")}',
        f'reply_id: {payload.get("reply_id")}',
        f'reply_from_agent: {payload.get("reply_from_agent")}',
        f'reply_terminal_status: {payload.get("reply_terminal_status")}',
        f'reply_notice: {str(bool(payload.get("reply_notice"))).lower()}',
        f'reply_notice_kind: {payload.get("reply_notice_kind")}',
        f'reply_finished_at: {payload.get("reply_finished_at")}',
        f'mailbox_state: {mailbox.get("mailbox_state")}',
        f'queue_depth: {mailbox.get("queue_depth")}',
        f'pending_reply_count: {mailbox.get("pending_reply_count")}',
        f'next_inbound_event_id: {payload.get("next_inbound_event_id")}',
        f'next_event_type: {payload.get("next_event_type")}',
    ]
    if payload.get('reply_last_progress_at') is not None:
        lines.append(f'reply_last_progress_at: {payload.get("reply_last_progress_at")}')
    if payload.get('reply_heartbeat_silence_seconds') is not None:
        lines.append(f'reply_heartbeat_silence_seconds: {payload.get("reply_heartbeat_silence_seconds")}')
    lines.append(f'reply: {_display_text(payload.get("reply"))}')
    return tuple(lines)


def render_watch_batch(batch) -> tuple[str, ...]:
    lines: list[str] = []
    for event in batch.events:
        target = event.get('target_name') or event.get('agent_name')
        lines.append(
            f'event: {event["event_id"]} {event["job_id"]} {target} {event["type"]} {event["timestamp"]}'
        )
    if batch.terminal:
        target = getattr(batch, 'target_name', '') or getattr(batch, 'agent_name', '')
        lines.extend(
            [
                'watch_status: terminal',
                f'job_id: {batch.job_id}',
                f'agent_name: {batch.agent_name}',
                f'target_name: {target}',
                f'status: {batch.status}',
                f'reply: {_display_text(batch.reply)}',
            ]
        )
    return tuple(lines)


def render_cancel(payload: Mapping[str, object]) -> tuple[str, ...]:
    return ('cancel_status: ok', *render_mapping(payload))


def render_logs(summary) -> tuple[str, ...]:
    lines = [
        'logs_status: ok',
        f'project_id: {summary.project_id}',
        f'agent_name: {summary.agent_name}',
        f'provider: {summary.provider}',
        f'runtime_ref: {summary.runtime_ref}',
        f'session_ref: {summary.session_ref}',
        f'log_count: {len(summary.entries)}',
    ]
    if not summary.entries:
        lines.append('log: <none>')
        return tuple(lines)
    for entry in summary.entries:
        lines.append(f'log: {entry.source} {entry.path}')
        for line in entry.lines:
            lines.append(f'log_line: {line}')
    return tuple(lines)


def render_doctor_bundle(summary) -> tuple[str, ...]:
    lines = [
        'doctor_bundle_status: ok',
        f'project: {summary.project_root}',
        f'project_id: {summary.project_id}',
        f'bundle_id: {summary.bundle_id}',
        f'bundle_path: {summary.bundle_path}',
        f'file_count: {summary.file_count}',
        f'included_count: {summary.included_count}',
        f'missing_count: {summary.missing_count}',
        f'truncated_count: {summary.truncated_count}',
        f'doctor_error: {summary.doctor_error}',
    ]
    return tuple(lines)


def render_kill(summary) -> tuple[str, ...]:
    lines = [
        'kill_status: ok',
        f'project_id: {summary.project_id}',
        f'state: {summary.state}',
        f'socket_path: {summary.socket_path}',
        f'forced: {str(summary.forced).lower()}',
    ]
    lines.extend(_render_tmux_cleanup_summaries(getattr(summary, 'cleanup_summaries', ()) or ()))
    return tuple(lines)


def render_open(summary) -> tuple[str, ...]:
    return (
        'open_status: ok',
        f'project_id: {summary.project_id}',
        f'tmux_socket_path: {summary.tmux_socket_path}',
        f'tmux_session_name: {summary.tmux_session_name}',
    )


def _render_tmux_cleanup_summaries(items: Sequence[object]) -> tuple[str, ...]:
    lines: list[str] = []
    for item in items:
        socket_name = _cleanup_field(getattr(item, 'socket_name', None), default='<default>')
        owned = _cleanup_csv(getattr(item, 'owned_panes', ()) or ())
        active = _cleanup_csv(getattr(item, 'active_panes', ()) or ())
        orphaned = _cleanup_csv(getattr(item, 'orphaned_panes', ()) or ())
        killed = _cleanup_csv(getattr(item, 'killed_panes', ()) or ())
        lines.append(
            'tmux_cleanup: '
            f'socket={socket_name} owned={owned} active={active} orphaned={orphaned} killed={killed}'
        )
    return tuple(lines)


def _cleanup_csv(items: Iterable[object]) -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    return ','.join(values) if values else '-'


def _cleanup_field(value: object, *, default: str) -> str:
    text = str(value or '').strip()
    return text or default


def render_ps(payload: Mapping[str, object]) -> tuple[str, ...]:
    lines = [
        f'project_id: {payload["project_id"]}',
        f'ccbd_state: {payload["ccbd_state"]}',
    ]
    for agent in payload['agents']:
        lines.append(
            f'agent: name={agent["agent_name"]} state={agent["state"]} provider={agent["provider"]} queue={agent["queue_depth"]}'
        )
        lines.append(
            f'binding: status={agent["binding_status"]} runtime={agent["runtime_ref"]} session={agent["session_ref"]} '
            f'source={agent.get("binding_source")} workspace={agent["workspace_path"]} terminal={agent.get("terminal")} '
            f'socket={agent.get("tmux_socket_name")} socket_path={agent.get("tmux_socket_path")} '
            f'pane={agent.get("pane_id")} active_pane={agent.get("active_pane_id")} '
            f'pane_state={agent.get("pane_state")} marker={agent.get("pane_title_marker")}'
        )
    return tuple(lines)


def render_doctor(payload: Mapping[str, object]) -> tuple[str, ...]:
    ccbd = payload['ccbd']
    lines = [
        f'project: {payload["project"]}',
        f'project_id: {payload["project_id"]}',
        f'ccbd_state: {ccbd["state"]}',
        f'ccbd_health: {ccbd["health"]}',
        f'ccbd_generation: {ccbd["generation"]}',
        f'ccbd_last_heartbeat_at: {ccbd["last_heartbeat_at"]}',
        f'ccbd_pid_alive: {ccbd["pid_alive"]}',
        f'ccbd_socket_connectable: {ccbd["socket_connectable"]}',
        f'ccbd_heartbeat_fresh: {ccbd["heartbeat_fresh"]}',
        f'ccbd_takeover_allowed: {ccbd["takeover_allowed"]}',
        f'ccbd_reason: {ccbd["reason"]}',
        f'ccbd_active_execution_count: {ccbd["active_execution_count"]}',
        f'ccbd_recoverable_execution_count: {ccbd["recoverable_execution_count"]}',
        f'ccbd_nonrecoverable_execution_count: {ccbd["nonrecoverable_execution_count"]}',
        f'ccbd_pending_items_count: {ccbd["pending_items_count"]}',
        f'ccbd_terminal_pending_count: {ccbd["terminal_pending_count"]}',
        f'ccbd_recoverable_execution_providers: {ccbd["recoverable_execution_providers"]}',
        f'ccbd_nonrecoverable_execution_providers: {ccbd["nonrecoverable_execution_providers"]}',
        f'ccbd_last_restore_at: {ccbd.get("last_restore_at")}',
        f'ccbd_last_restore_running_job_count: {ccbd.get("last_restore_running_job_count")}',
        f'ccbd_last_restore_restored_execution_count: {ccbd.get("last_restore_restored_execution_count")}',
        f'ccbd_last_restore_replay_pending_count: {ccbd.get("last_restore_replay_pending_count")}',
        f'ccbd_last_restore_terminal_pending_count: {ccbd.get("last_restore_terminal_pending_count")}',
        f'ccbd_last_restore_abandoned_execution_count: {ccbd.get("last_restore_abandoned_execution_count")}',
        f'ccbd_last_restore_already_active_count: {ccbd.get("last_restore_already_active_count")}',
        f'ccbd_last_restore_results_text: {ccbd.get("last_restore_results_text")}',
        f'ccbd_startup_last_at: {ccbd.get("startup_last_at")}',
        f'ccbd_startup_last_trigger: {ccbd.get("startup_last_trigger")}',
        f'ccbd_startup_last_status: {ccbd.get("startup_last_status")}',
        f'ccbd_startup_last_generation: {ccbd.get("startup_last_generation")}',
        f'ccbd_startup_last_daemon_started: {ccbd.get("startup_last_daemon_started")}',
        f'ccbd_startup_last_requested_agents: {ccbd.get("startup_last_requested_agents")}',
        f'ccbd_startup_last_desired_agents: {ccbd.get("startup_last_desired_agents")}',
        f'ccbd_startup_last_actions: {ccbd.get("startup_last_actions")}',
        f'ccbd_startup_last_cleanup_killed: {ccbd.get("startup_last_cleanup_killed")}',
        f'ccbd_startup_last_failure_reason: {ccbd.get("startup_last_failure_reason")}',
        f'ccbd_startup_last_agent_results_text: {ccbd.get("startup_last_agent_results_text")}',
        f'ccbd_shutdown_last_at: {ccbd.get("shutdown_last_at")}',
        f'ccbd_shutdown_last_trigger: {ccbd.get("shutdown_last_trigger")}',
        f'ccbd_shutdown_last_status: {ccbd.get("shutdown_last_status")}',
        f'ccbd_shutdown_last_forced: {ccbd.get("shutdown_last_forced")}',
        f'ccbd_shutdown_last_generation: {ccbd.get("shutdown_last_generation")}',
        f'ccbd_shutdown_last_reason: {ccbd.get("shutdown_last_reason")}',
        f'ccbd_shutdown_last_stopped_agents: {ccbd.get("shutdown_last_stopped_agents")}',
        f'ccbd_shutdown_last_actions: {ccbd.get("shutdown_last_actions")}',
        f'ccbd_shutdown_last_cleanup_killed: {ccbd.get("shutdown_last_cleanup_killed")}',
        f'ccbd_shutdown_last_failure_reason: {ccbd.get("shutdown_last_failure_reason")}',
        f'ccbd_shutdown_last_runtime_states_text: {ccbd.get("shutdown_last_runtime_states_text")}',
        f'ccbd_namespace_epoch: {ccbd.get("namespace_epoch")}',
        f'ccbd_namespace_tmux_socket_path: {ccbd.get("namespace_tmux_socket_path")}',
        f'ccbd_namespace_tmux_session_name: {ccbd.get("namespace_tmux_session_name")}',
        f'ccbd_namespace_layout_version: {ccbd.get("namespace_layout_version")}',
        f'ccbd_namespace_ui_attachable: {ccbd.get("namespace_ui_attachable")}',
        f'ccbd_namespace_last_started_at: {ccbd.get("namespace_last_started_at")}',
        f'ccbd_namespace_last_destroyed_at: {ccbd.get("namespace_last_destroyed_at")}',
        f'ccbd_namespace_last_destroy_reason: {ccbd.get("namespace_last_destroy_reason")}',
        f'ccbd_namespace_last_event_kind: {ccbd.get("namespace_last_event_kind")}',
        f'ccbd_namespace_last_event_at: {ccbd.get("namespace_last_event_at")}',
        f'ccbd_namespace_last_event_epoch: {ccbd.get("namespace_last_event_epoch")}',
        f'ccbd_namespace_last_event_socket_path: {ccbd.get("namespace_last_event_socket_path")}',
        f'ccbd_namespace_last_event_session_name: {ccbd.get("namespace_last_event_session_name")}',
        f'ccbd_start_policy_auto_permission: {ccbd.get("start_policy_auto_permission")}',
        f'ccbd_start_policy_recovery_restore: {ccbd.get("start_policy_recovery_restore")}',
        f'ccbd_start_policy_last_started_at: {ccbd.get("start_policy_last_started_at")}',
        f'ccbd_start_policy_source: {ccbd.get("start_policy_source")}',
        f'ccbd_tmux_cleanup_last_kind: {ccbd.get("tmux_cleanup_last_kind")}',
        f'ccbd_tmux_cleanup_last_at: {ccbd.get("tmux_cleanup_last_at")}',
        f'ccbd_tmux_cleanup_socket_count: {ccbd.get("tmux_cleanup_socket_count")}',
        f'ccbd_tmux_cleanup_total_owned: {ccbd.get("tmux_cleanup_total_owned")}',
        f'ccbd_tmux_cleanup_total_active: {ccbd.get("tmux_cleanup_total_active")}',
        f'ccbd_tmux_cleanup_total_orphaned: {ccbd.get("tmux_cleanup_total_orphaned")}',
        f'ccbd_tmux_cleanup_total_killed: {ccbd.get("tmux_cleanup_total_killed")}',
        f'ccbd_tmux_cleanup_sockets: {ccbd.get("tmux_cleanup_sockets")}',
    ]
    for error in ccbd.get('diagnostic_errors') or ():
        lines.append(f'ccbd_diagnostic_error: {error}')
    for agent in payload['agents']:
        lines.append(
            f'agent: name={agent["agent_name"]} health={agent["health"]} provider={agent["provider"]} completion={agent["completion_family"]}'
        )
        lines.append(
            f'binding: status={agent["binding_status"]} runtime={agent["runtime_ref"]} session={agent["session_ref"]} '
            f'source={agent.get("binding_source")} workspace={agent["workspace_path"]} terminal={agent.get("terminal")} '
            f'socket={agent.get("tmux_socket_name")} socket_path={agent.get("tmux_socket_path")} '
            f'pane={agent.get("pane_id")} active_pane={agent.get("active_pane_id")} '
            f'pane_state={agent.get("pane_state")} marker={agent.get("pane_title_marker")}'
        )
        lines.append(
            f'restore: supported={agent["execution_resume_supported"]} mode={agent["execution_restore_mode"]} reason={agent["execution_restore_reason"]}'
        )
        lines.append(f'restore_detail: {agent["execution_restore_detail"]}')
    return tuple(lines)


def render_fault_list(summary) -> tuple[str, ...]:
    lines = [
        'fault_status: ok',
        f'project_id: {summary.project_id}',
        f'rule_count: {summary.rule_count}',
    ]
    if not summary.rules:
        lines.append('fault_rule: <none>')
        return tuple(lines)
    for rule in summary.rules:
        lines.append(
            'fault_rule: '
            f'id={rule.rule_id} agent={rule.agent_name} task={rule.task_id} '
            f'reason={rule.reason} remaining={rule.remaining_count} '
            f'created={rule.created_at} updated={rule.updated_at} '
            f'error={rule.error_message}'
        )
    return tuple(lines)


def render_fault_arm(summary) -> tuple[str, ...]:
    return (
        'fault_status: armed',
        f'project_id: {summary.project_id}',
        f'rule_id: {summary.rule_id}',
        f'agent_name: {summary.agent_name}',
        f'task_id: {summary.task_id}',
        f'reason: {summary.reason}',
        f'remaining_count: {summary.remaining_count}',
        f'error_message: {summary.error_message}',
    )


def render_fault_clear(summary) -> tuple[str, ...]:
    lines = [
        'fault_status: cleared',
        f'project_id: {summary.project_id}',
        f'target: {summary.target}',
        f'cleared_count: {summary.cleared_count}',
    ]
    for rule_id in summary.cleared_rule_ids:
        lines.append(f'cleared_rule_id: {rule_id}')
    return tuple(lines)


def write_lines(out, lines: Iterable[str]) -> None:
    for line in lines:
        print(line, file=out)
