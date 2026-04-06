from __future__ import annotations

from pathlib import Path
from typing import TextIO

from cli.ask_usage import write_ask_usage
from cli.auxiliary import cmd_droid_subcommand
from cli.management import cmd_reinstall, cmd_uninstall, cmd_update, cmd_version
from cli.phase2 import maybe_handle_phase2
from cli.router import dispatch_auxiliary_command, dispatch_management_command, print_start_help


def _should_print_version(tokens: list[str]) -> bool:
    return "--print-version" in tokens


def _is_ask_help(tokens: list[str]) -> bool:
    return len(tokens) >= 2 and tokens[0] == "ask" and tokens[1] in {"-h", "--help", "help"}


def _is_help(tokens: list[str]) -> bool:
    return bool(tokens and tokens[0] in {"-h", "--help", "help"})


def _rewrite_version_alias(tokens: list[str]) -> list[str]:
    if tokens and tokens[0] in {"-v", "--version"}:
        return ["version"]
    return tokens


def _write_removed_command_error(stderr: TextIO, *, command: str, guidance: str) -> int:
    print(f"❌ `ccb {command}` has been removed.", file=stderr)
    print(guidance, file=stderr)
    return 2


def _handle_help(tokens: list[str], *, stdout: TextIO) -> int | None:
    if _is_ask_help(tokens):
        write_ask_usage(stdout, command_name="ccb ask")
        return 0
    if _is_help(tokens):
        print_start_help(file=stdout)
        return 0
    return None


def _handle_removed_commands(tokens: list[str], *, stderr: TextIO) -> int | None:
    if tokens and tokens[0] == "up":
        print("❌ `ccb up` is no longer supported.", file=stderr)
        print("💡 Use: ccb [agents...]  (configured by .ccb/ccb.config)", file=stderr)
        return 2

    if tokens and tokens[0] in {"mail", "provider"}:
        return _write_removed_command_error(
            stderr,
            command=tokens[0],
            guidance="💡 Use `ccb ask`, `ccb ping`, `ccb pend`, `ccb ps`, `ccb logs`, or `ccb doctor`.",
        )
    return None


def _dispatch_auxiliary(tokens: list[str], *, script_root: Path) -> int | None:
    return dispatch_auxiliary_command(
        tokens,
        droid_handler=lambda args: cmd_droid_subcommand(list(args), script_root=script_root),
    )


def _dispatch_management(tokens: list[str], *, script_root: Path) -> int | None:
    if not (tokens and tokens[0] in {"version", "update", "uninstall", "reinstall"}):
        return None

    return dispatch_management_command(
        tokens,
        kill_handler=_unsupported_kill_handler,
        update_handler=lambda args: cmd_update(args, script_root=script_root),
        version_handler=lambda args: cmd_version(args, script_root=script_root),
        uninstall_handler=lambda args: cmd_uninstall(args, script_root=script_root),
        reinstall_handler=lambda args: cmd_reinstall(args, script_root=script_root),
    )


def run_cli_entrypoint(
    argv: list[str],
    *,
    version: str,
    script_root: Path,
    cwd: Path,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    tokens = list(argv or [])
    if _should_print_version(tokens):
        print(f"v{version}", file=stdout)
        return 0

    help_result = _handle_help(tokens, stdout=stdout)
    if help_result is not None:
        return help_result

    tokens = _rewrite_version_alias(tokens)

    removed_result = _handle_removed_commands(tokens, stderr=stderr)
    if removed_result is not None:
        return removed_result

    auxiliary_result = _dispatch_auxiliary(tokens, script_root=script_root)
    if auxiliary_result is not None:
        return auxiliary_result

    management_result = _dispatch_management(tokens, script_root=script_root)
    if management_result is not None:
        return management_result

    return maybe_handle_phase2(tokens, cwd=cwd, stdout=stdout, stderr=stderr)


def _unsupported_kill_handler(_args) -> int:
    return 2


__all__ = ["run_cli_entrypoint"]
