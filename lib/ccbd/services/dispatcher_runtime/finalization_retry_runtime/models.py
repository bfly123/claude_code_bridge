from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutomaticRetryPlan:
    message_id: str
    attempt_id: str
    attempt_number: int
    max_attempts: int
    reason: str


@dataclass(frozen=True)
class RetryableFailureContext:
    message_id: str
    attempt_id: str
    attempt_number: int
    max_attempts: int
    reason: str


__all__ = ['AutomaticRetryPlan', 'RetryableFailureContext']
