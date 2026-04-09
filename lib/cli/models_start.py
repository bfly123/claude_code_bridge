from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedStartCommand:
    project: str | None
    agent_names: tuple[str, ...]
    restore: bool
    auto_permission: bool
    reset_context: bool = False
    kind: str = 'start'


@dataclass(frozen=True)
class ParsedOpenCommand:
    project: str | None
    kind: str = 'open'


@dataclass(frozen=True)
class ParsedKillCommand:
    project: str | None
    force: bool = False
    kind: str = 'kill'


@dataclass(frozen=True)
class ParsedPsCommand:
    project: str | None
    alive_only: bool = False
    kind: str = 'ps'


@dataclass(frozen=True)
class ParsedConfigValidateCommand:
    project: str | None
    kind: str = 'config-validate'


@dataclass(frozen=True)
class ParsedDoctorCommand:
    project: str | None
    bundle: bool = False
    output_path: str | None = None
    kind: str = 'doctor'


@dataclass(frozen=True)
class ParsedLogsCommand:
    project: str | None
    agent_name: str
    kind: str = 'logs'


@dataclass(frozen=True)
class ParsedPingCommand:
    project: str | None
    target: str
    kind: str = 'ping'


__all__ = [
    'ParsedConfigValidateCommand',
    'ParsedDoctorCommand',
    'ParsedKillCommand',
    'ParsedLogsCommand',
    'ParsedOpenCommand',
    'ParsedPingCommand',
    'ParsedPsCommand',
    'ParsedStartCommand',
]
