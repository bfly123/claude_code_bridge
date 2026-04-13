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
        ["update", "5.3.0"],
        update_handler=make_handler("update"),
        version_handler=make_handler("version"),
        uninstall_handler=make_handler("uninstall"),
        reinstall_handler=make_handler("reinstall"),
    )

    assert result == 1
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "update"
    assert args.command == "update"
    assert args.target == "5.3.0"


def test_dispatch_management_command_returns_none_for_non_management() -> None:
    def fail(_args: argparse.Namespace) -> int:
        raise AssertionError("handler should not be called")

    assert dispatch_management_command(
        ["codex", "claude"],
        update_handler=fail,
        version_handler=fail,
        uninstall_handler=fail,
        reinstall_handler=fail,
    ) is None


def test_parse_start_args_defaults_resume_and_auto_and_supports_new_context() -> None:
    args = parse_start_args(["-n", "-s"])
    assert args.resume is True
    assert args.auto is True
    assert args.new_context is True
    assert args.safe is True


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
    assert "usage: ccb [-s] [-n]" in stdout.getvalue()
    assert "Primary workflow:" in stdout.getvalue()
    assert "ccb -s" in stdout.getvalue()
    assert "Model control plane:" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_run_cli_entrypoint_prints_kill_help() -> None:
    stdout = StringIO()
    stderr = StringIO()

    result = run_cli_entrypoint(
        ["kill", "--help"],
        version="5.2.8",
        script_root=Path("/tmp/ccb"),
        cwd=Path("/tmp/project"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert "usage: ccb kill [-f]" in stdout.getvalue()
    assert "Project runtime cleanup:" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_run_cli_entrypoint_prints_start_help_for_start_flags() -> None:
    stdout = StringIO()
    stderr = StringIO()

    result = run_cli_entrypoint(
        ["-s", "--help"],
        version="5.2.8",
        script_root=Path("/tmp/ccb"),
        cwd=Path("/tmp/project"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert "usage: ccb [-s] [-n]" in stdout.getvalue()
    assert "Primary workflow:" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_run_cli_entrypoint_prints_ping_help() -> None:
    stdout = StringIO()
    stderr = StringIO()

    result = run_cli_entrypoint(
        ["ping", "--help"],
        version="5.2.8",
        script_root=Path("/tmp/ccb"),
        cwd=Path("/tmp/project"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert "usage: ccb ping <agent|all|ccbd>" in stdout.getvalue()
    assert "Control-plane health:" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_run_cli_entrypoint_prints_watch_help_with_project_prefix() -> None:
    stdout = StringIO()
    stderr = StringIO()

    result = run_cli_entrypoint(
        ["--project", "/tmp/demo", "watch", "--help"],
        version="5.2.8",
        script_root=Path("/tmp/ccb"),
        cwd=Path("/tmp/project"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert "usage: ccb watch <agent|job_id>" in stdout.getvalue()
    assert "Live reply stream:" in stdout.getvalue()
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
