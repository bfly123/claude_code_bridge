"""Terminal status helpers shared across provider runtimes."""

from __future__ import annotations

COMPLETION_STATUS_COMPLETED = "completed"
COMPLETION_STATUS_CANCELLED = "cancelled"
COMPLETION_STATUS_FAILED = "failed"
COMPLETION_STATUS_INCOMPLETE = "incomplete"

VALID_COMPLETION_STATUSES = {
    COMPLETION_STATUS_COMPLETED,
    COMPLETION_STATUS_CANCELLED,
    COMPLETION_STATUS_FAILED,
    COMPLETION_STATUS_INCOMPLETE,
}

COMPLETION_STATUS_LABELS = {
    COMPLETION_STATUS_COMPLETED: "Completed",
    COMPLETION_STATUS_CANCELLED: "Cancelled",
    COMPLETION_STATUS_FAILED: "Failed",
    COMPLETION_STATUS_INCOMPLETE: "Incomplete",
}

COMPLETION_STATUS_MARKERS = {
    COMPLETION_STATUS_COMPLETED: "[CCB_TASK_COMPLETED]",
    COMPLETION_STATUS_CANCELLED: "[CCB_TASK_CANCELLED]",
    COMPLETION_STATUS_FAILED: "[CCB_TASK_FAILED]",
    COMPLETION_STATUS_INCOMPLETE: "[CCB_TASK_INCOMPLETE]",
}

def normalize_completion_status(status: str | None, *, done_seen: bool = True) -> str:
    raw = (status or "").strip().lower()
    if raw in VALID_COMPLETION_STATUSES:
        return raw
    return COMPLETION_STATUS_COMPLETED if done_seen else COMPLETION_STATUS_INCOMPLETE


def completion_status_label(status: str | None, *, done_seen: bool = True) -> str:
    normalized = normalize_completion_status(status, done_seen=done_seen)
    return COMPLETION_STATUS_LABELS[normalized]


def completion_status_marker(status: str | None, *, done_seen: bool = True) -> str:
    normalized = normalize_completion_status(status, done_seen=done_seen)
    return COMPLETION_STATUS_MARKERS[normalized]


def default_reply_for_status(status: str | None, *, done_seen: bool = True) -> str:
    normalized = normalize_completion_status(status, done_seen=done_seen)
    if normalized == COMPLETION_STATUS_CANCELLED:
        return "Task cancelled or timed out before completion."
    if normalized == COMPLETION_STATUS_FAILED:
        return "Task failed before producing a complete reply."
    if normalized == COMPLETION_STATUS_INCOMPLETE:
        return "Task ended without a confirmed completion marker."
    return ""
