from __future__ import annotations

from pathlib import Path
from typing import TextIO

from cli.ask_usage import write_ask_usage
from cli.auxiliary import cmd_droid_subcommand
from cli.management import cmd_reinstall, cmd_uninstall, cmd_update, cmd_version
from cli.phase2 import maybe_handle_phase2
from cli.parser_runtime.constants import SUBCOMMANDS
from cli.router import dispatch_auxiliary_command, dispatch_management_command, print_command_help, print_kill_help, print_start_help


def _should_print_version(tokens: list[str]) -> bool:
    return "--print-version" in tokens


def _is_ask_help(tokens: list[str]) -> bool:
    visible = _strip_global_project_tokens(tokens)
    return len(visible) >= 2 and visible[0] == "ask" and visible[1] in {"-h", "--help", "help"}


def _is_kill_help(tokens: list[str]) -> bool:
    visible = _strip_global_project_tokens(tokens)
    return len(visible) >= 2 and visible[0] == "kill" and visible[1] in {"-h", "--help", "help"}


def _is_start_help(tokens: list[str]) -> bool:
    tokens = _strip_global_project_tokens(tokens)
    if not tokens:
        return False
    if tokens[0] in {"-h", "--help", "help"}:
        return True
    if tokens[0] in SUBCOMMANDS or tokens[0] in {"version", "update", "uninstall", "reinstall", "droid", "mail", "provider", "up"}:
        return False
    return any(token in {"-h", "--help", "help"} for token in tokens)


def _command_help_name(tokens: list[str]) -> str | None:
    visible = _strip_global_project_tokens(tokens)
    if len(visible) == 2 and visible[1] in {"-h", "--help"}:
        return visible[0]
    return None


def _strip_global_project_tokens(tokens: list[str]) -> list[str]:
    remaining = list(tokens)
    while remaining[:1] == ["--project"] and len(remaining) >= 2:
        remaining = remaining[2:]
    return remaining


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
    if _is_kill_help(tokens):
        print_kill_help(file=stdout)
        return 0
    command_name = _command_help_name(tokens)
    if command_name is not None and print_command_help(command_name, file=stdout):
        return 0
    if _is_start_help(tokens):
        print_start_help(file=stdout)
        return 0
    return None


def _handle_removed_commands(tokens: list[str], *, stderr: TextIO) -> int | None:
    if tokens and tokens[0] == "up":
        print("❌ `ccb up` is no longer supported.", file=stderr)
        print("💡 Use: ccb  (agents are configured by .ccb/ccb.config)", file=stderr)
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
__all__ = ["run_cli_entrypoint"]
