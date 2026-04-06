from __future__ import annotations


def latest_replies(payload: dict) -> tuple[int, tuple[dict, ...], int, int]:
    latest_attempts = latest_attempt_map(payload.get('attempts') or ())
    replies_by_attempt = latest_reply_map(payload.get('replies') or ())
    replies = materialized_replies(latest_attempts, replies_by_attempt)
    replies.sort(key=reply_sort_key)
    notice_count = notice_reply_count(replies)
    terminal_count = len(replies) - notice_count
    return len(latest_attempts), tuple(replies), terminal_count, notice_count


def latest_attempt_map(attempts) -> dict[tuple[str, str], dict]:
    latest_attempts: dict[tuple[str, str], dict] = {}
    for attempt in attempts:
        key = attempt_identity(attempt)
        current = latest_attempts.get(key)
        if current is None or attempt_sort_key(attempt) > attempt_sort_key(current):
            latest_attempts[key] = attempt
    return latest_attempts


def latest_reply_map(replies) -> dict[str, dict]:
    replies_by_attempt: dict[str, dict] = {}
    for reply in replies:
        attempt_id = str(reply.get('attempt_id') or '')
        if not attempt_id:
            continue
        current = replies_by_attempt.get(attempt_id)
        if current is None or reply_sort_key(reply) > reply_sort_key(current):
            replies_by_attempt[attempt_id] = reply
    return replies_by_attempt


def materialized_replies(
    latest_attempts: dict[tuple[str, str], dict],
    replies_by_attempt: dict[str, dict],
) -> list[dict]:
    replies: list[dict] = []
    for attempt in latest_attempts.values():
        reply = reply_for_attempt(attempt, replies_by_attempt)
        if reply is not None:
            replies.append(reply)
    return replies


def reply_for_attempt(
    attempt: dict,
    replies_by_attempt: dict[str, dict],
) -> dict | None:
    reply = replies_by_attempt.get(str(attempt.get('attempt_id') or ''))
    if reply is None:
        return None
    notice = bool(reply.get('notice'))
    return {
        'reply_id': reply.get('reply_id'),
        'message_id': reply.get('message_id'),
        'attempt_id': reply.get('attempt_id'),
        'agent_name': reply.get('agent_name'),
        'job_id': attempt.get('job_id'),
        'terminal_status': reply.get('terminal_status'),
        'notice': notice,
        'notice_kind': reply.get('notice_kind'),
        'last_progress_at': reply.get('last_progress_at'),
        'heartbeat_silence_seconds': reply.get('heartbeat_silence_seconds'),
        'reason': reply.get('reason'),
        'finished_at': reply.get('finished_at'),
        'reply': reply.get('reply') or '',
    }


def notice_reply_count(replies: list[dict]) -> int:
    return sum(1 for reply in replies if bool(reply.get('notice')))


def attempt_identity(attempt: dict) -> tuple[str, str]:
    return (
        str(attempt.get('message_id') or ''),
        str(attempt.get('agent_name') or ''),
    )


def attempt_sort_key(attempt: dict) -> tuple[int, str, str]:
    return (
        int(attempt.get('retry_index') or 0),
        str(attempt.get('updated_at') or ''),
        str(attempt.get('attempt_id') or ''),
    )


def reply_sort_key(reply: dict) -> tuple[str, str]:
    return str(reply.get('finished_at') or ''), str(reply.get('reply_id') or '')


__all__ = ['attempt_sort_key', 'latest_replies', 'reply_sort_key']
