from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

_logger = logging.getLogger(__name__)

# cmd delivery telemetry.
#
# Writes JSONL records to `.ccb/metrics/body_read_followup.jsonl` so rollout
# health can be measured post-hoc. Best-effort only — any write failure is
# swallowed so telemetry never blocks delivery.
#
# Three event families are recorded:
#   header_only_dispatch         long reply went out via the pointer path
#   long_reply_fell_back_full_body  long reply degraded to full-body; reason
#                                   names why (kill_switch_disabled,
#                                   project_root_unavailable, ...)
#   cmd_phase2_failure           claim succeeded but plan or inject raised;
#                                reply is either recoverable on disk or lost
#
# Without these fallback/failure events, the 1-2 week observation window can
# silently lie about rollout health — a degrade or a crash would look like a
# clean full-body pass. See codex structural review 2026-04-22.

_METRICS_SUBDIR = ('metrics',)
_METRICS_FILE = 'body_read_followup.jsonl'


def metrics_path(project_root: Path) -> Path:
    return Path(project_root) / '.ccb' / _METRICS_SUBDIR[0] / _METRICS_FILE


def _append_record(project_root: Optional[Path], record: dict) -> None:
    if project_root is None:
        # Nothing to write to; drop silently. The warning in the caller is
        # enough — don't create a telemetry blackhole dependency.
        return
    try:
        target = metrics_path(Path(project_root))
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception:
        _logger.debug('cmd-delivery telemetry write failed', exc_info=True)


def record_header_only_dispatch(
    project_root: Path,
    *,
    reply_id: str,
    body_file: Path,
    dispatched_at: str,
    body_char_count: int,
) -> None:
    _append_record(project_root, {
        'schema_version': 1,
        'event': 'header_only_dispatch',
        'reply_id': reply_id,
        'body_file': str(body_file),
        'dispatched_at': dispatched_at,
        'body_char_count': body_char_count,
    })


def record_long_reply_fallback(
    project_root: Optional[Path],
    *,
    reply_id: str,
    reason: str,
    body_char_count: int,
    dispatched_at: str,
) -> None:
    """Record when a long body degraded to full-body delivery.

    `reason` values come from CmdDeliveryFallback.reason — e.g.
    'kill_switch_disabled', 'project_root_unavailable'. Cheap to add new
    reasons; the reader just groups by string.
    """
    _append_record(project_root, {
        'schema_version': 1,
        'event': 'long_reply_fell_back_full_body',
        'reply_id': reply_id,
        'reason': reason,
        'body_char_count': body_char_count,
        'dispatched_at': dispatched_at,
    })


def record_phase2_failure(
    project_root: Optional[Path],
    *,
    reply_id: str,
    stage: str,
    reason: str,
    body_char_count: int,
    failed_at: str,
) -> None:
    """Record a post-claim failure (plan or inject raised after claim).

    `stage` is 'plan' or 'send'. These events are rare but load-bearing:
    they let you distinguish "reply was lost because tmux hiccuped" from
    "reply fell back to full body as designed".
    """
    _append_record(project_root, {
        'schema_version': 1,
        'event': 'cmd_phase2_failure',
        'reply_id': reply_id,
        'stage': stage,
        'reason': reason,
        'body_char_count': body_char_count,
        'failed_at': failed_at,
    })


__all__ = [
    'metrics_path',
    'record_header_only_dispatch',
    'record_long_reply_fallback',
    'record_phase2_failure',
]
