from __future__ import annotations

from typing import TextIO
import os


def ask_wait_timeout_seconds() -> float:
    raw = str(os.environ.get("CCB_ASK_WAIT_TIMEOUT_S") or "3600").strip()
    try:
        return float(raw)
    except ValueError:
        return 3600.0


def ask_wait_poll_interval_seconds() -> float:
    raw = str(os.environ.get("CCB_ASK_WAIT_POLL_INTERVAL_S") or "0.1").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.1


def write_ask_usage(
    out: TextIO,
    *,
    command_name: str,
    error: str | None = None,
    alias_note: str | None = None,
) -> None:
    if error:
        print(f"error: {error}", file=out)
        print("", file=out)
    print("Usage:", file=out)
    print(
        f"  {command_name} [--wait|--sync|--async] [--output FILE|-o FILE] [--timeout SECONDS|-t SECONDS]",
        file=out,
    )
    print(
        "      [--silence] <target> [--] <message...>",
        file=out,
    )
    print("      sender is inferred from the current workspace agent and falls back to user", file=out)
    print("      message text may be supplied on stdin", file=out)
    print(f"  {command_name} wait <job_id>", file=out)
    print(f"  {command_name} get <job_id>", file=out)
    print(f"  {command_name} cancel <job_id>", file=out)
    if alias_note:
        print("", file=out)
        print(alias_note, file=out)


__all__ = [
    "ask_wait_poll_interval_seconds",
    "ask_wait_timeout_seconds",
    "write_ask_usage",
]
