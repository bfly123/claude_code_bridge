from __future__ import annotations

import logging
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .formatting import format_reply_delivery_body

# cmd-only transport planner.
#
# Decides whether a reply's body should be injected full (short) or sent as a
# header-only pointer with the body persisted to disk (long). Keeps this
# decision OUT of the shared reply formatter so agent-to-agent delivery stays
# on the existing contract. See codex structural review 2026-04-22.
#
# Threshold chosen from empirical measurement over 226 replies across 3 active
# CCB projects: median body is 2025 chars, p90 is 5013 chars, p95 is 5899
# chars. Cutting at 1500 removes 92.7% of total body bytes while affecting
# 67.7% of replies.

_logger = logging.getLogger(__name__)

_BODY_CHAR_THRESHOLD = 1500
_SUMMARY_LINES = 3
_SUMMARY_LINE_MAX = 160

# Kill switch. Set CCB_HEADER_ONLY=0 (or false/no/off) to force full-body
# delivery for every cmd reply. Read on every call so toggling the env var and
# restarting the daemon takes effect without editing code.
_KILL_SWITCH_ENV = 'CCB_HEADER_ONLY'
_KILL_SWITCH_FALSY = frozenset({'0', 'false', 'no', 'off', ''})


def header_only_enabled() -> bool:
    raw = os.environ.get(_KILL_SWITCH_ENV)
    if raw is None:
        return True
    return str(raw).strip().lower() not in _KILL_SWITCH_FALSY


@dataclass(frozen=True)
class CmdDeliveryPlan:
    body: str                # text to inject into cmd tmux pane
    header_only: bool        # True when long-body path was taken
    body_file: Path | None   # absolute path where body was persisted, when header_only


@dataclass(frozen=True)
class CmdDeliveryFallback:
    """Records why a long-body reply did NOT take the header-only path.

    Returned as the second tuple element of `plan_cmd_delivery`. `None` means
    header-only was taken (when plan.header_only is True) or the reply was
    short/heartbeat (when plan.header_only is False and fallback is None).
    When a long reply falls back to full-body, this object names the reason
    so telemetry and debugging are not flying blind.
    """
    reason: str
    body_char_count: int


def plan_cmd_delivery(
    dispatcher,
    reply,
    *,
    project_root: Optional[Path],
    body_store,
) -> tuple['CmdDeliveryPlan', Optional['CmdDeliveryFallback']]:
    full_body = format_reply_delivery_body(dispatcher, reply)
    if _is_heartbeat(reply):
        # Heartbeats are small by construction and semantically must arrive
        # intact (silence notices, job status). Never truncate.
        return CmdDeliveryPlan(body=full_body, header_only=False, body_file=None), None

    raw_body = str(reply.reply or '')
    if len(raw_body) <= _BODY_CHAR_THRESHOLD:
        # Short-body path does not require project_root; preserves pre-B
        # warm-cache short-inject behavior when layout is temporarily missing.
        return CmdDeliveryPlan(body=full_body, header_only=False, body_file=None), None

    if not header_only_enabled():
        # Kill switch off: force full-body regardless of length.
        _logger.debug(
            'cmd reply %s is long (%d chars) but header-only is disabled via '
            '%s — falling back to full-body inject',
            reply.reply_id, len(raw_body), _KILL_SWITCH_ENV,
        )
        return (
            CmdDeliveryPlan(body=full_body, header_only=False, body_file=None),
            CmdDeliveryFallback(reason='kill_switch_disabled', body_char_count=len(raw_body)),
        )

    if project_root is None:
        # Long body but no place to persist — degrade gracefully to full body.
        # Costs transcript bloat on this one reply but keeps delivery working.
        # Telemetry surfaces this so the observation window cannot lie about
        # header-only adoption (codex structural review 2026-04-22).
        _logger.warning(
            'cmd reply %s is long (%d chars) but project_root is unavailable — '
            'falling back to full-body inject', reply.reply_id, len(raw_body),
        )
        return (
            CmdDeliveryPlan(body=full_body, header_only=False, body_file=None),
            CmdDeliveryFallback(reason='project_root_unavailable', body_char_count=len(raw_body)),
        )

    # Long path: persist full body, replace transcript payload with
    # header + body_file pointer + 3-line summary. Must run in phase 2.
    body_file = body_store.write_reply_body(project_root, reply.reply_id, raw_body)
    header_only_body = _build_header_only_body(
        dispatcher=dispatcher,
        reply=reply,
        body_file=body_file,
        raw_body=raw_body,
    )
    return (
        CmdDeliveryPlan(body=header_only_body, header_only=True, body_file=body_file),
        None,
    )


def _build_header_only_body(*, dispatcher, reply, body_file: Path, raw_body: str) -> str:
    header_tokens = [
        'CCB_REPLY',
        f'from={reply.agent_name}',
        f'reply={reply.reply_id}',
        f'status={reply.terminal_status.value}',
    ]
    source_job = _source_job(dispatcher, reply)
    if source_job is not None:
        header_tokens.append(f'job={source_job.job_id}')
        task_id = str(source_job.request.task_id or '').strip()
        if task_id:
            header_tokens.append(f'task={task_id}')
    # shlex.quote preserves CCB_REPLY token boundaries even when body_file
    # path contains spaces or shell metacharacters.
    quoted_body_file = shlex.quote(str(body_file))
    header_tokens.append(f'body_file={quoted_body_file}')
    header_tokens.append('must_read=1')

    # Structured, machine-parseable notice. Per codex structural review
    # 2026-04-22: prose notices are easy to skim past; key=value tokens on
    # their own line mirror the CCB_REPLY header and repeat must_read=1 so
    # the hard signal cannot be missed. The human-readable hint sits below
    # as orientation only.
    notice_line = (
        f'CCB_NOTICE kind=external_body must_read=1 body_file={quoted_body_file}'
    )
    human_hint = (
        'Call the Read tool on body_file before responding. '
        'Preview below is a 3-line excerpt; the full reply is on disk.'
    )

    summary = _extract_summary(raw_body)
    parts = [
        ' '.join(header_tokens),
        notice_line,
        human_hint,
        '',
        summary,
    ]
    return '\n'.join(parts).rstrip()


def _extract_summary(body: str) -> str:
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) > _SUMMARY_LINE_MAX:
            stripped = stripped[: _SUMMARY_LINE_MAX - 1] + '…'
        lines.append(stripped)
        if len(lines) >= _SUMMARY_LINES:
            break
    if not lines:
        return '(long body — see body_file)'
    lines.append('')
    lines.append('(body truncated; read body_file for full content)')
    return '\n'.join(lines)


# Local helpers — intentionally duplicated from formatting.py so this planner
# survives any formatting.py refactor without silently breaking. See codex
# review adjust #2.

def _is_heartbeat(reply) -> bool:
    diagnostics = getattr(reply, 'diagnostics', {}) or {}
    return str(diagnostics.get('notice_kind') or '').strip().lower() == 'heartbeat'


def _source_job(dispatcher, reply):
    try:
        attempt_store = dispatcher._message_bureau_control._attempt_store
    except AttributeError:
        return None
    attempt = attempt_store.get_latest(reply.attempt_id)
    if attempt is None:
        return None
    source_job = dispatcher.get_job(attempt.job_id) if hasattr(dispatcher, 'get_job') else None
    if source_job is not None:
        return source_job
    try:
        from ..records import get_job
    except ImportError:
        return None
    return get_job(dispatcher, attempt.job_id)


__all__ = [
    'CmdDeliveryPlan',
    'CmdDeliveryFallback',
    'header_only_enabled',
    'plan_cmd_delivery',
]
