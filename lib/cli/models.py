from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class ParsedStartCommand:
    project: str | None
    agent_names: tuple[str, ...]
    restore: bool
    auto_permission: bool
    reset_context: bool = False
    kind: str = 'start'


@dataclass(frozen=True)
class ParsedAskCommand:
    project: str | None
    target: str
    sender: str | None
    message: str
    task_id: str | None = None
    reply_to: str | None = None
    mode: str | None = None
    silence: bool = False
    wait: bool = False
    output_path: str | None = None
    timeout_s: float | None = None
    kind: str = 'ask'


@dataclass(frozen=True)
class ParsedCancelCommand:
    project: str | None
    job_id: str
    kind: str = 'cancel'


@dataclass(frozen=True)
class ParsedKillCommand:
    project: str | None
    force: bool = False
    kind: str = 'kill'


@dataclass(frozen=True)
class ParsedOpenCommand:
    project: str | None
    kind: str = 'open'


@dataclass(frozen=True)
class ParsedPsCommand:
    project: str | None
    alive_only: bool = False
    kind: str = 'ps'


@dataclass(frozen=True)
class ParsedPingCommand:
    project: str | None
    target: str
    kind: str = 'ping'


@dataclass(frozen=True)
class ParsedAskWaitCommand:
    project: str | None
    job_id: str
    timeout_s: float | None = None
    kind: str = 'ask-wait'


@dataclass(frozen=True)
class ParsedWatchCommand:
    project: str | None
    target: str
    kind: str = 'watch'


@dataclass(frozen=True)
class ParsedPendCommand:
    project: str | None
    target: str
    count: int | None = None
    kind: str = 'pend'


@dataclass(frozen=True)
class ParsedQueueCommand:
    project: str | None
    target: str
    kind: str = 'queue'


@dataclass(frozen=True)
class ParsedTraceCommand:
    project: str | None
    target: str
    kind: str = 'trace'


@dataclass(frozen=True)
class ParsedResubmitCommand:
    project: str | None
    message_id: str
    kind: str = 'resubmit'


@dataclass(frozen=True)
class ParsedRetryCommand:
    project: str | None
    target: str
    kind: str = 'retry'


@dataclass(frozen=True)
class ParsedWaitCommand:
    project: str | None
    mode: str
    target: str
    quorum: int | None = None
    timeout_s: float | None = None
    kind: str = 'wait'


@dataclass(frozen=True)
class ParsedInboxCommand:
    project: str | None
    agent_name: str
    kind: str = 'inbox'


@dataclass(frozen=True)
class ParsedAckCommand:
    project: str | None
    agent_name: str
    inbound_event_id: str | None = None
    kind: str = 'ack'


@dataclass(frozen=True)
class ParsedLogsCommand:
    project: str | None
    agent_name: str
    kind: str = 'logs'


@dataclass(frozen=True)
class ParsedDoctorCommand:
    project: str | None
    bundle: bool = False
    output_path: str | None = None
    kind: str = 'doctor'


@dataclass(frozen=True)
class ParsedFaultListCommand:
    project: str | None
    kind: str = 'fault-list'


@dataclass(frozen=True)
class ParsedFaultArmCommand:
    project: str | None
    agent_name: str
    task_id: str
    reason: str
    count: int
    error_message: str
    kind: str = 'fault-arm'


@dataclass(frozen=True)
class ParsedFaultClearCommand:
    project: str | None
    target: str
    kind: str = 'fault-clear'


@dataclass(frozen=True)
class ParsedConfigValidateCommand:
    project: str | None
    kind: str = 'config-validate'


ParsedCommand = Union[
    ParsedAckCommand,
    ParsedAskCommand,
    ParsedAskWaitCommand,
    ParsedCancelCommand,
    ParsedConfigValidateCommand,
    ParsedDoctorCommand,
    ParsedFaultArmCommand,
    ParsedFaultClearCommand,
    ParsedFaultListCommand,
    ParsedInboxCommand,
    ParsedKillCommand,
    ParsedLogsCommand,
    ParsedOpenCommand,
    ParsedPendCommand,
    ParsedPingCommand,
    ParsedPsCommand,
    ParsedQueueCommand,
    ParsedResubmitCommand,
    ParsedRetryCommand,
    ParsedStartCommand,
    ParsedTraceCommand,
    ParsedWaitCommand,
    ParsedWatchCommand,
]
