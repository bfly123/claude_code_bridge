from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from textwrap import dedent


AuxiliaryHandler = Callable[[Sequence[str]], int]
ManagementHandler = Callable[[argparse.Namespace], int]

_MANAGEMENT_COMMANDS = {"update", "version", "uninstall", "reinstall"}


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
            usage: ccb [-s] [-n]

            Primary workflow:
              ccb                  Start project agents from `.ccb/ccb.config`.
              ccb -s               Safe start. Disable CLI auto-permission override.
              ccb -n               Rebuild .ccb except ccb.config, then start fresh.
              ccb kill             Stop the current project's background runtime.
              ccb kill -f          Force cleanup project-owned runtime residue.

            Model control plane:
              ccb ask <agent> [from <sender>] <message>
              ccb ping <agent|ccbd>
              ccb pend <agent|job_id> [N]
              ccb watch <agent|job_id>

            Advanced diagnostics:
              ccb ps | ccb logs <agent> | ccb doctor
              ccb version | ccb update | ccb uninstall | ccb reinstall
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
              - `kill` still works when `.ccb` exists but `ccb.config` is missing or stale.
              - Use `ccb -n` after `ccb kill` when you want to rebuild `.ccb` but keep `ccb.config`.
            """
        ).strip(),
        file=file,
    )


def print_command_help(command_name: str, *, file=None) -> bool:
    text = _COMMAND_HELP.get(command_name)
    if text is None:
        return False
    print(dedent(text).strip(), file=file)
    return True


_COMMAND_HELP = {
    "ping": """
        usage: ccb ping <agent|all|ccbd>

        Control-plane health:
          ccb ping <agent>   Show runtime health for one named agent.
          ccb ping all       Show mounted-agent health across the project.
          ccb ping ccbd      Show project daemon health.
    """,
    "pend": """
        usage: ccb pend <agent|job_id> [N]

        Reply inspection:
          ccb pend <agent>      Show the latest reply for one agent mailbox.
          ccb pend <job_id>     Show the latest reply for one submitted job.
          ccb pend <target> N   Show the latest N replies.
    """,
    "watch": """
        usage: ccb watch <agent|job_id>

        Live reply stream:
          ccb watch <agent>   Stream the current mailbox/reply state for one agent.
          ccb watch <job_id>  Stream job events until terminal completion or timeout.
    """,
    "logs": """
        usage: ccb logs <agent>

        Runtime diagnostics:
          ccb logs <agent>   Tail the current runtime/session log for one agent.
    """,
    "ps": """
        usage: ccb ps

        Runtime inventory:
          ccb ps   Show known runtime/session/workspace bindings.
    """,
    "doctor": """
        usage: ccb doctor [--output [PATH]]

        Diagnostics bundle:
          ccb doctor               Print project diagnostic summary.
          ccb doctor --output      Export a support bundle to the default path.
          ccb doctor --output PATH Export a support bundle to PATH.
    """,
    "cancel": """
        usage: ccb cancel <job_id>

        Job control:
          ccb cancel <job_id>   Request cancellation for a submitted job.
    """,
    "config": """
        usage: ccb config validate

        Config validation:
          ccb config validate   Validate `.ccb/ccb.config` for the current project.
    """,
}


def _build_management_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ccb", description="Claude AI unified launcher", add_help=True)
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

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
    start_parser.add_argument("-s", "--safe", action="store_true", default=False, help=argparse.SUPPRESS)
    start_parser.add_argument(
        "-n",
        "--new-context",
        dest="new_context",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return start_parser
