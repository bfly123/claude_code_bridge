from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence, TextIO

from agents.config_loader import ConfigValidationError
from cli.parser import CliParser, CliUsageError
from project.discovery import ProjectDiscoveryError


def error_prefix(*, kind: str, config_command: bool) -> str:
    if kind == 'invalid':
        return 'config_status: invalid' if config_command else 'command_status: invalid'
    return 'config_status: invalid' if config_command else 'command_status: failed'


def print_phase2_error(
    err: TextIO,
    *,
    kind: str,
    config_command: bool,
    exc: Exception,
) -> None:
    print(
        f'{error_prefix(kind=kind, config_command=config_command)}\nerror: {exc}',
        file=err,
    )


def parse_phase2_command(
    argv: Sequence[str],
    *,
    config_command: bool,
    err: TextIO,
):
    try:
        return CliParser().parse(list(argv))
    except CliUsageError as exc:
        print_phase2_error(
            err,
            kind='invalid',
            config_command=config_command,
            exc=exc,
        )
        return None


def handle_phase2_exception(err: TextIO, *, command_kind: str, exc: Exception) -> int:
    is_config = command_kind == 'config-validate'
    print_phase2_error(
        err,
        kind='failed',
        config_command=is_config,
        exc=exc,
    )
    if isinstance(exc, ProjectDiscoveryError):
        return 2 if is_config else 1
    if isinstance(
        exc,
        (
            ConfigValidationError,
            RuntimeError,
            ValueError,
            KeyError,
            subprocess.SubprocessError,
        ),
    ):
        return 1
    raise exc


__all__ = [
    'handle_phase2_exception',
    'parse_phase2_command',
    'print_phase2_error',
]
