"""
Codex communication module (log-driven version)
Sends requests via FIFO and parses replies from the effective Codex session root.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from provider_sessions.watch import HAS_WATCHDOG, SessionFileWatcher
from terminal_runtime.backend_env import apply_backend_env
from .comm_runtime import (
    SESSION_ID_PATTERN,
    ensure_codex_watchdog_started as _ensure_watchdog_started,
    current_session_root,
    extract_cwd_from_log_file as _extract_cwd_from_log_file,
    extract_cwd_from_log as _extract_cwd_from_log_impl,
    extract_session_id as _extract_session_id,
    find_codex_session_file,
    handle_codex_log_event as _handle_watchdog_event,
    publish_registry_binding,
    resolve_unique_codex_session_target as _resolve_unique_codex_session_target,
    update_project_session_binding,
)
from .comm_runtime.communicator_facade import CodexCommunicator
from .comm_runtime.log_reader_facade import CodexLogReader

apply_backend_env()

__all__ = [
    "CodexCommunicator",
    "CodexLogReader",
    "SESSION_ID_PATTERN",
    "main",
]

_CODEX_WATCHER: Optional[SessionFileWatcher] = None
_CODEX_WATCH_STARTED = False
_CODEX_WATCH_LOCK = threading.Lock()


def _handle_codex_log_event(path: Path) -> None:
    try:
        from .session import load_project_session
    except Exception:
        return

    _handle_watchdog_event(
        path,
        cwd_extractor=_extract_cwd_from_log_file,
        session_resolver=lambda work_dir: _resolve_unique_codex_session_target(work_dir, log_path=path),
        session_loader=load_project_session,
        session_id_extractor=CodexCommunicator._extract_session_id,
    )


def _ensure_codex_watchdog_started() -> None:
    global _CODEX_WATCHER, _CODEX_WATCH_STARTED
    _CODEX_WATCHER, _CODEX_WATCH_STARTED = _ensure_watchdog_started(
        has_watchdog=HAS_WATCHDOG,
        started=_CODEX_WATCH_STARTED,
        lock=_CODEX_WATCH_LOCK,
        session_root=current_session_root(),
        watcher_factory=SessionFileWatcher,
        event_handler=_handle_codex_log_event,
        watcher=_CODEX_WATCHER,
    )


_ensure_codex_watchdog_started()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Codex communication tool (log-driven)")
    parser.add_argument("question", nargs="*", help="Question to send")
    parser.add_argument("--wait", "-w", action="store_true", help="Wait for reply synchronously")
    parser.add_argument("--timeout", type=int, default=30, help="Sync timeout in seconds")
    parser.add_argument("--ping", action="store_true", help="Test connectivity")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--pending", nargs="?", const=1, type=int, metavar="N",
                        help="Show pending reply (optionally last N conversations)")

    args = parser.parse_args()

    try:
        comm = CodexCommunicator()

        if args.ping:
            comm.ping()
        elif args.status:
            status = comm.get_status()
            print("📊 Codex status:")
            for key, value in status.items():
                print(f"   {key}: {value}")
        elif args.pending is not None:
            comm.consume_pending(n=args.pending)
        elif args.question:
            tokens = list(args.question)
            if tokens and tokens[0].lower() == "ask":
                tokens = tokens[1:]
            question_text = " ".join(tokens).strip()
            if not question_text:
                print("❌ Please provide a question")
                return 1
            if args.wait:
                comm.ask_sync(question_text, args.timeout)
            else:
                comm.ask_async(question_text)
        else:
            print("Please provide a question or use --ping/--status/--pending options")
            return 1
        return 0
    except Exception as exc:
        print(f"❌ Execution failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
