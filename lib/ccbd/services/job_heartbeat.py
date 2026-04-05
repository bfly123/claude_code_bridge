from __future__ import annotations

from ccbd.api_models import JobRecord, JobStatus, TargetKind
from ccbd.system import utc_now
from heartbeat import HeartbeatAction, HeartbeatPolicy, HeartbeatStateStore, evaluate_heartbeat
from mailbox_targets import known_mailbox_targets, normalize_mailbox_target
from storage.paths import PathLayout

_DEFAULT_SUBJECT_KIND = 'job_progress'
_TRACKED_MESSAGE_TYPES = frozenset({'ask'})


class JobHeartbeatService:
    def __init__(
        self,
        layout: PathLayout,
        *,
        policy: HeartbeatPolicy,
        store: HeartbeatStateStore | None = None,
        clock=utc_now,
        subject_kind: str = _DEFAULT_SUBJECT_KIND,
    ) -> None:
        self._layout = layout
        self._policy = policy
        self._store = store or HeartbeatStateStore(layout)
        self._clock = clock
        self._subject_kind = str(subject_kind or _DEFAULT_SUBJECT_KIND).strip() or _DEFAULT_SUBJECT_KIND

    def tick(self, dispatcher) -> tuple[str, ...]:
        active_job_ids: set[str] = set()
        for _target_kind, _target_name, job_id in dispatcher._state.active_items():
            job = dispatcher.get(job_id)
            if not self._should_track(job):
                continue
            active_job_ids.add(job.job_id)
            self._tick_job(dispatcher, job)
        self._cleanup_inactive(active_job_ids)
        return tuple(sorted(active_job_ids))

    def _should_track(self, job: JobRecord | None) -> bool:
        if job is None or job.status is not JobStatus.RUNNING:
            return False
        if job.target_kind is not TargetKind.AGENT:
            return False
        message_type = str(job.request.message_type or '').strip().lower()
        return message_type in _TRACKED_MESSAGE_TYPES

    def _tick_job(self, dispatcher, job: JobRecord) -> None:
        snapshot = dispatcher.get_snapshot(job.job_id)
        observed_last_progress_at = (
            str(snapshot.updated_at).strip()
            if snapshot is not None and str(snapshot.updated_at).strip()
            else str(job.updated_at).strip()
        )
        if not observed_last_progress_at:
            return
        prior_state = self._store.load(self._subject_kind, job.job_id)
        now = self._clock()
        next_state, decision = evaluate_heartbeat(
            policy=self._policy,
            subject_kind=self._subject_kind,
            subject_id=job.job_id,
            owner=job.agent_name,
            observed_last_progress_at=observed_last_progress_at,
            now=now,
            state=prior_state,
        )
        if decision.action is HeartbeatAction.RESET:
            self._store.save(next_state)
            dispatcher._append_event(
                job,
                'job_heartbeat_reset',
                {
                    'subject_kind': self._subject_kind,
                    'action': decision.action.value,
                    'notice_count': decision.notice_count,
                    'last_progress_at': decision.last_progress_at,
                },
                timestamp=now,
            )
            return
        if not decision.notice_due:
            return

        mailbox_target = normalize_mailbox_target(
            job.request.from_actor,
            known_targets=known_mailbox_targets(dispatcher._config),
        )
        diagnostics = _heartbeat_diagnostics(
            job,
            decision=decision,
            snapshot=snapshot,
            mailbox_target=mailbox_target,
            subject_kind=self._subject_kind,
        )
        if dispatcher._message_bureau is None or mailbox_target is None:
            self._store.save(next_state)
            dispatcher._append_event(
                job,
                'job_heartbeat_skipped_no_mailbox',
                diagnostics,
                timestamp=now,
            )
            return

        reply_id = dispatcher._message_bureau.record_notice(
            job,
            reply=_heartbeat_notice_body(job, decision=decision, snapshot=snapshot),
            diagnostics=diagnostics,
            finished_at=now,
            deliver_to_actor=mailbox_target,
        )
        self._store.save(next_state)
        dispatcher._append_event(
            job,
            'job_heartbeat_notice_sent',
            {
                **diagnostics,
                'reply_id': reply_id,
            },
            timestamp=now,
        )

    def _cleanup_inactive(self, active_job_ids: set[str]) -> None:
        for state in self._store.list_all(subject_kind=self._subject_kind):
            if state.subject_id in active_job_ids:
                continue
            self._store.remove(state.subject_kind, state.subject_id)


def _heartbeat_notice_body(job: JobRecord, *, decision, snapshot) -> str:
    lines = [
        'CCB_HEARTBEAT '
        f'from={job.agent_name} '
        f'job={job.job_id} '
        f'notice={decision.notice_count} '
        f'silent_for={_format_silence(decision.silence_seconds)} '
        f'last_progress={decision.last_progress_at}',
    ]
    task_id = str(job.request.task_id or '').strip()
    if task_id:
        lines[0] = f'{lines[0]} task={task_id}'
    preview = _snapshot_preview(snapshot)
    if preview:
        lines.extend(['', preview])
    return '\n'.join(lines).rstrip()


def _heartbeat_diagnostics(
    job: JobRecord,
    *,
    decision,
    snapshot,
    mailbox_target: str | None,
    subject_kind: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        'notice': True,
        'notice_kind': 'heartbeat',
        'heartbeat_subject_kind': subject_kind,
        'heartbeat_action': decision.action.value,
        'heartbeat_notice_count': decision.notice_count,
        'heartbeat_silence_seconds': round(float(decision.silence_seconds), 3),
        'last_progress_at': decision.last_progress_at,
        'job_id': job.job_id,
        'task_id': str(job.request.task_id or '').strip() or None,
        'caller_actor': job.request.from_actor,
        'caller_mailbox': mailbox_target,
    }
    preview = _snapshot_preview(snapshot)
    if preview:
        payload['reply_preview'] = preview
    return payload


def _snapshot_preview(snapshot) -> str:
    if snapshot is None:
        return ''
    return str(snapshot.latest_reply_preview or '').strip()


def _format_silence(value: float) -> str:
    try:
        seconds = int(round(float(value)))
    except Exception:
        return str(value)
    return f'{seconds}s'


__all__ = ['JobHeartbeatService']
