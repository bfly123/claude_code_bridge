from __future__ import annotations

from pathlib import Path
import sys
from typing import TextIO

from cli.ask_usage import write_ask_usage
from cli.auxiliary import cmd_droid_subcommand
from cli.management import cmd_reinstall, cmd_uninstall, cmd_update, cmd_version
from cli.router import dispatch_auxiliary_command, dispatch_management_command, print_start_help
from cli.phase2 import maybe_handle_phase2


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
    if "--print-version" in tokens:
        print(f"v{version}", file=stdout)
        return 0

    if len(tokens) >= 2 and tokens[0] == "ask" and tokens[1] in {"-h", "--help", "help"}:
        write_ask_usage(stdout, command_name="ccb ask")
        return 0

    if tokens and tokens[0] in {"-h", "--help", "help"}:
        print_start_help(file=stdout)
        return 0

    if tokens and tokens[0] in {"-v", "--version"}:
        tokens = ["version"]

    if tokens and tokens[0] == "up":
        print("❌ `ccb up` is no longer supported.", file=stderr)
        print("💡 Use: ccb [agents...]  (configured by .ccb/ccb.config)", file=stderr)
        return 2

    if tokens and tokens[0] in {"mail", "provider"}:
        print(f"❌ `ccb {tokens[0]}` has been removed.", file=stderr)
        print("💡 Use `ccb ask`, `ccb ping`, `ccb pend`, `ccb ps`, `ccb logs`, or `ccb doctor`.", file=stderr)
        return 2

    auxiliary_result = dispatch_auxiliary_command(
        tokens,
        droid_handler=lambda args: cmd_droid_subcommand(list(args), script_root=script_root),
    )
    if auxiliary_result is not None:
        return auxiliary_result

    if tokens and tokens[0] in {"version", "update", "uninstall", "reinstall"}:
        management_result = dispatch_management_command(
            tokens,
            kill_handler=_unsupported_kill_handler,
            update_handler=lambda args: cmd_update(args, script_root=script_root),
            version_handler=lambda args: cmd_version(args, script_root=script_root),
            uninstall_handler=lambda args: cmd_uninstall(args, script_root=script_root),
            reinstall_handler=lambda args: cmd_reinstall(args, script_root=script_root),
        )
        if management_result is not None:
            return management_result

    return maybe_handle_phase2(tokens, cwd=cwd, stdout=stdout, stderr=stderr)


def _unsupported_kill_handler(_args) -> int:
    return 2
