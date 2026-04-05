from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path

from cli.entrypoint import run_cli_entrypoint
from cli.router import (
    dispatch_auxiliary_command,
    dispatch_management_command,
    parse_start_args,
)


def test_dispatch_auxiliary_command_routes_droid_only() -> None:
    calls: list[tuple[str, list[str]]] = []

    def droid_handler(argv):
        calls.append(("droid", list(argv)))
        return 11

    assert dispatch_auxiliary_command(
        ["droid", "setup-delegation"],
        droid_handler=droid_handler,
    ) == 11
    assert dispatch_auxiliary_command(
        ["version"],
        droid_handler=droid_handler,
    ) is None
    assert calls == [("droid", ["setup-delegation"])]


def test_dispatch_management_command_parses_and_routes() -> None:
    calls: list[tuple[str, argparse.Namespace]] = []

    def make_handler(name: str):
        def _handler(args: argparse.Namespace) -> int:
            calls.append((name, args))
            return len(calls)
        return _handler

    result = dispatch_management_command(
        ["kill", "codex", "claude", "--force", "--yes"],
        kill_handler=make_handler("kill"),
        update_handler=make_handler("update"),
        version_handler=make_handler("version"),
        uninstall_handler=make_handler("uninstall"),
        reinstall_handler=make_handler("reinstall"),
    )

    assert result == 1
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "kill"
    assert args.command == "kill"
    assert args.providers == ["codex", "claude"]
    assert args.force is True
    assert args.yes is True


def test_dispatch_management_command_returns_none_for_non_management() -> None:
    def fail(_args: argparse.Namespace) -> int:
        raise AssertionError("handler should not be called")

    assert dispatch_management_command(
        ["codex", "claude"],
        kill_handler=fail,
        update_handler=fail,
        version_handler=fail,
        uninstall_handler=fail,
        reinstall_handler=fail,
    ) is None


def test_parse_start_args_defaults_resume_and_auto_and_supports_new_context() -> None:
    args = parse_start_args(["codex", "claude", "-n"])
    assert args.providers == ["codex", "claude"]
    assert args.resume is True
    assert args.auto is True
    assert args.new_context is True


def test_run_cli_entrypoint_prints_start_help_without_phase2() -> None:
    stdout = StringIO()
    stderr = StringIO()

    result = run_cli_entrypoint(
        ["--help"],
        version="5.2.8",
        script_root=Path("/tmp/ccb"),
        cwd=Path("/tmp/project"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert "usage: ccb" in stdout.getvalue()
    assert "Other commands:" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_run_cli_entrypoint_prints_ask_help() -> None:
    stdout = StringIO()
    stderr = StringIO()

    result = run_cli_entrypoint(
        ["ask", "--help"],
        version="5.2.8",
        script_root=Path("/tmp/ccb"),
        cwd=Path("/tmp/project"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert "Usage:" in stdout.getvalue()
    assert "ccb ask [--wait|--sync|--async]" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_run_cli_entrypoint_rejects_removed_provider_command() -> None:
    stdout = StringIO()
    stderr = StringIO()

    result = run_cli_entrypoint(
        ["provider", "ping", "--help"],
        version="5.2.8",
        script_root=Path("/tmp/ccb"),
        cwd=Path("/tmp/project"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 2
    assert stdout.getvalue() == ""
    assert "`ccb provider` has been removed" in stderr.getvalue()


def test_run_cli_entrypoint_rejects_removed_mail_command() -> None:
    stdout = StringIO()
    stderr = StringIO()

    result = run_cli_entrypoint(
        ["mail", "status"],
        version="5.2.8",
        script_root=Path("/tmp/ccb"),
        cwd=Path("/tmp/project"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 2
    assert stdout.getvalue() == ""
    assert "`ccb mail` has been removed" in stderr.getvalue()
