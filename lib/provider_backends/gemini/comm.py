"""
Gemini communication module
Uses tmux-backed sessions and reads replies from ~/.gemini/tmp/<hash>/chats/session-*.json
"""

from __future__ import annotations
import threading
from pathlib import Path
from typing import Optional

from provider_sessions.watch import HAS_WATCHDOG, SessionFileWatcher
from terminal_runtime.backend_env import apply_backend_env
from .comm_runtime import (
    GEMINI_ROOT,
    ensure_gemini_watchdog_started as _ensure_watchdog_started,
    handle_gemini_session_event as _handle_watchdog_event,
    publish_registry_binding,
    read_gemini_session_id as _read_gemini_session_id,
    update_project_session_binding,
    work_dirs_for_hash as _work_dirs_for_hash,
)
from .comm_runtime.communicator_facade import GeminiCommunicator
from .comm_runtime.log_reader_facade import GeminiLogReader

from .session import find_project_session_file as find_gemini_project_session_file

apply_backend_env()

_GEMINI_WATCHER: Optional[SessionFileWatcher] = None
_GEMINI_WATCH_STARTED = False
_GEMINI_WATCH_LOCK = threading.Lock()


def _handle_gemini_session_event(path: Path) -> None:
    try:
        from .session import load_project_session
    except Exception:
        return

    _handle_watchdog_event(
        path,
        gemini_root=GEMINI_ROOT,
        work_dirs_for_hash=_work_dirs_for_hash,
        session_id_reader=_read_gemini_session_id,
        session_file_finder=find_gemini_project_session_file,
        session_loader=load_project_session,
    )


def _ensure_gemini_watchdog_started() -> None:
    global _GEMINI_WATCHER, _GEMINI_WATCH_STARTED
    _GEMINI_WATCHER, _GEMINI_WATCH_STARTED = _ensure_watchdog_started(
        has_watchdog=HAS_WATCHDOG,
        started=_GEMINI_WATCH_STARTED,
        lock=_GEMINI_WATCH_LOCK,
        gemini_root=GEMINI_ROOT,
        watcher_factory=SessionFileWatcher,
        event_handler=_handle_gemini_session_event,
        watcher=_GEMINI_WATCHER,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Gemini communication tool")
    parser.add_argument("question", nargs="*", help="Question to send")
    parser.add_argument("--wait", "-w", action="store_true", help="Wait for reply synchronously")
    parser.add_argument("--timeout", type=int, default=60, help="Sync timeout in seconds")
    parser.add_argument("--ping", action="store_true", help="Test connectivity")
    parser.add_argument("--status", action="store_true", help="View status")
    parser.add_argument("--pending", nargs="?", const=1, type=int, metavar="N",
                        help="View pending reply (optionally last N conversations)")

    args = parser.parse_args()

    try:
        comm = GeminiCommunicator()

        if args.ping:
            comm.ping()
        elif args.status:
            status = comm.get_status()
            print("📊 Gemini status:")
            for key, value in status.items():
                print(f"   {key}: {value}")
        elif args.pending is not None:
            comm.consume_pending(n=args.pending)
        elif args.question:
            question_text = " ".join(args.question).strip()
            if not question_text:
                print("❌ Please provide a question")
                return 1
            if args.wait:
                comm.ask_sync(question_text, args.timeout)
            else:
                comm.ask_async(question_text)
        else:
            print("Please provide a question or use --ping/--status/--pending")
            return 1
        return 0
    except Exception as exc:
        print(f"❌ Execution failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
