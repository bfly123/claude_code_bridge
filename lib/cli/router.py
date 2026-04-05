from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence


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
    build_start_parser().print_help(file=file)


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
        add_help=True,
        epilog=(
            "Interactive terminals auto-open the project UI after start. "
            "Use `ccb open` to reattach later. "
            "Other commands: ccb update | ccb version | ccb kill | ccb uninstall | "
            "ccb reinstall | ccb droid setup-delegation | ccb ping | ccb pend"
        ),
    )
    start_parser.add_argument(
        "providers",
        nargs="*",
        metavar="agent",
        help="Named agents to start (space separated), resolved from .ccb/ccb.config",
    )
    start_parser.add_argument("-r", "--resume", "--restore", action="store_true", default=True, help="Resume context (default on)")
    start_parser.add_argument("-a", "--auto", action="store_true", default=True, help="Full auto permission mode (default on)")
    start_parser.add_argument(
        "-n",
        "--new-context",
        dest="new_context",
        action="store_true",
        help="Rebuild all project-owned .ccb state except ccb.config, then start fresh with confirmation",
    )
    return start_parser
