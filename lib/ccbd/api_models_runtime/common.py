from __future__ import annotations

from enum import Enum


SCHEMA_VERSION = 2
API_VERSION = 2


class JobStatus(str, Enum):
    ACCEPTED = "accepted"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class DeliveryScope(str, Enum):
    SINGLE = "single"
    BROADCAST = "broadcast"


class TargetKind(str, Enum):
    AGENT = "agent"


__all__ = ["API_VERSION", "SCHEMA_VERSION", "DeliveryScope", "JobStatus", "TargetKind"]
