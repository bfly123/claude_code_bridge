from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from textwrap import dedent


AuxiliaryHandler = Callable[[Sequence[str]], int]
ManagementHandler = Callable[[argparse.Namespace], int]

_MANAGEMENT_COMMANDS = {"kill", "update", "version", "uninstall", "reinstall"}


def dispatch_auxiliary_command(
    argv: Sequence[str],
    *,
    droid_handler: AuxiliaryHandler,
) -> int | None:
    tokens = list(argv)
    if tokens and tokens[0] == "droid" and len(tokens) > 1 and tokens[1] in {"setup-delegation", "test-delegation"}:
        return droid_handler(tokens[1:])
    return None


def dispatch_management_command(
    argv: Sequence[str],
    *,
    kill_handler: ManagementHandler,
    update_handler: ManagementHandler,
    version_handler: ManagementHandler,
    uninstall_handler: ManagementHandler,
    reinstall_handler: ManagementHandler,
) -> int | None:
    tokens = list(argv)
    if not tokens or tokens[0] not in _MANAGEMENT_COMMANDS:
        return None

    parser = _build_management_parser()
    args = parser.parse_args(tokens)
    if args.command == "kill":
        return kill_handler(args)
    if args.command == "update":
        return update_handler(args)
    if args.command == "version":
        return version_handler(args)
    if args.command == "uninstall":
        return uninstall_handler(args)
    if args.command == "reinstall":
        return reinstall_handler(args)
    parser.print_help()
    return 1


def parse_start_args(argv: Sequence[str]) -> argparse.Namespace:
    return build_start_parser().parse_args(list(argv))


def print_start_help(*, file=None) -> None:
    print(
        dedent(
            """
            usage: ccb [-s] [-n] [agent ...]

            Primary workflow:
              ccb [agent ...]      Start project agents with restore + auto permissions.
              ccb -s [agent ...]   Safe start. Disable CLI auto-permission override.
              ccb -n [agent ...]   Rebuild .ccb except ccb.config, then start fresh.
              ccb kill             Stop the current project's background runtime.
              ccb kill -f          Force cleanup project-owned runtime residue.

            Model control plane:
              ccb ask <agent> [from <sender>] <message>
              ccb ping <agent|ccbd>
              ccb pend <agent|job_id> [N]
              ccb watch <agent|job_id>

            Advanced diagnostics:
              ccb open | ccb ps | ccb logs <agent> | ccb doctor
              ccb version | ccb update | ccb uninstall | ccb reinstall

            Notes:
              - `ccb` already includes the old auto + restore path.
              - `ccb -s` matches the old non-`-a` behavior.
              - Legacy `-a` / `-r` are still accepted for compatibility but hidden from user help.
            """
        ).strip(),
        file=file,
    )


def print_kill_help(*, file=None) -> None:
    print(
        dedent(
            """
            usage: ccb kill [-f]

            Project runtime cleanup:
              ccb kill     Stop the current project's ccbd, agents, and tmux namespace.
              ccb kill -f  Force cleanup project-owned runtime residue before `ccb -n`.

            Notes:
              - `kill` is project-scoped. It does not bootstrap a missing `.ccb`.
              - Use `ccb -n` after `ccb kill` when you want to rebuild `.ccb` but keep `ccb.config`.
            """
        ).strip(),
        file=file,
    )


def _build_management_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ccb", description="Claude AI unified launcher", add_help=True)
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    kill_parser = subparsers.add_parser("kill", help="Terminate session or clean up zombies")
    kill_parser.add_argument("providers", nargs="*", default=[], help="Backends to terminate (codex/gemini/opencode/claude/droid)")
    kill_parser.add_argument("-f", "--force", action="store_true", help="Clean up all zombie tmux sessions globally")
    kill_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt (with -f)")

    update_parser = subparsers.add_parser("update", help="Update to latest or specified version")
    update_parser.add_argument("target", nargs="?", help="version like '4', '4.1', '4.1.3'")

    subparsers.add_parser("version", help="Show version and check for updates")
    subparsers.add_parser("uninstall", help="Uninstall ccb and clean configs")
    subparsers.add_parser("reinstall", help="Reinstall ccb and refresh configs")
    return parser


def build_start_parser() -> argparse.ArgumentParser:
    start_parser = argparse.ArgumentParser(
        prog="ccb",
        description="Claude AI unified launcher",
        add_help=False,
    )
    start_parser.add_argument(
        "providers",
        nargs="*",
        metavar="agent",
        help=argparse.SUPPRESS,
    )
    start_parser.add_argument("-r", "--resume", "--restore", action="store_true", default=True, help=argparse.SUPPRESS)
    start_parser.add_argument("-a", "--auto", action="store_true", default=True, help=argparse.SUPPRESS)
    start_parser.add_argument("-s", "--safe", action="store_true", default=False, help=argparse.SUPPRESS)
    start_parser.add_argument(
        "-n",
        "--new-context",
        dest="new_context",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return start_parser
