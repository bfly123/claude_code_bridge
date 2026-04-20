from __future__ import annotations

from pathlib import Path
from typing import TextIO
import sys

from cli.ask_usage import write_ask_usage
from cli.phase2 import maybe_handle_phase2


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    project_tokens, remaining = _extract_project_tokens(args)
    if remaining and remaining[0] in {"-h", "--help", "help"}:
        write_ask_usage(
            out,
            command_name="ask",
            alias_note="`ask` is a compatibility alias for `ccb ask`.",
        )
        return 0
    return maybe_handle_phase2([*project_tokens, "ask", *remaining], cwd=Path.cwd(), stdout=out, stderr=err)


def _extract_project_tokens(args: list[str]) -> tuple[list[str], list[str]]:
    remaining = list(args)
    project_tokens: list[str] = []
    while remaining and remaining[0] == "--project":
        if len(remaining) < 2:
            break
        project_tokens.extend(remaining[:2])
        remaining = remaining[2:]
    return project_tokens, remaining


__all__ = ["main"]
