"""
CCB Completion Hook - Async notification when CCB delegation tasks complete.

This module provides a function to notify Claude when a CCB task completes.
The notification is sent asynchronously to avoid blocking the daemon.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional


COMPLETION_STATUS_COMPLETED = "completed"
COMPLETION_STATUS_CANCELLED = "cancelled"
COMPLETION_STATUS_FAILED = "failed"
COMPLETION_STATUS_INCOMPLETE = "incomplete"

VALID_COMPLETION_STATUSES = {
    COMPLETION_STATUS_COMPLETED,
    COMPLETION_STATUS_CANCELLED,
    COMPLETION_STATUS_FAILED,
    COMPLETION_STATUS_INCOMPLETE,
}

COMPLETION_STATUS_LABELS = {
    COMPLETION_STATUS_COMPLETED: "Completed",
    COMPLETION_STATUS_CANCELLED: "Cancelled",
    COMPLETION_STATUS_FAILED: "Failed",
    COMPLETION_STATUS_INCOMPLETE: "Incomplete",
}

COMPLETION_STATUS_MARKERS = {
    COMPLETION_STATUS_COMPLETED: "[CCB_TASK_COMPLETED]",
    COMPLETION_STATUS_CANCELLED: "[CCB_TASK_CANCELLED]",
    COMPLETION_STATUS_FAILED: "[CCB_TASK_FAILED]",
    COMPLETION_STATUS_INCOMPLETE: "[CCB_TASK_INCOMPLETE]",
}


def env_bool(name: str, default: bool = True) -> bool:
    val = os.environ.get(name, "").strip().lower()
    if not val:
        return default
    return val not in ("0", "false", "no", "off")


def normalize_completion_status(status: str | None, *, done_seen: bool = True) -> str:
    raw = (status or "").strip().lower()
    if raw in VALID_COMPLETION_STATUSES:
        return raw
    return COMPLETION_STATUS_COMPLETED if done_seen else COMPLETION_STATUS_INCOMPLETE


def completion_status_label(status: str | None, *, done_seen: bool = True) -> str:
    normalized = normalize_completion_status(status, done_seen=done_seen)
    return COMPLETION_STATUS_LABELS[normalized]


def completion_status_marker(status: str | None, *, done_seen: bool = True) -> str:
    normalized = normalize_completion_status(status, done_seen=done_seen)
    return COMPLETION_STATUS_MARKERS[normalized]


def default_reply_for_status(status: str | None, *, done_seen: bool = True) -> str:
    normalized = normalize_completion_status(status, done_seen=done_seen)
    if normalized == COMPLETION_STATUS_CANCELLED:
        return "Task cancelled or timed out before completion."
    if normalized == COMPLETION_STATUS_FAILED:
        return "Task failed before producing a complete reply."
    if normalized == COMPLETION_STATUS_INCOMPLETE:
        return "Task ended without a confirmed completion marker."
    return ""


def _run_hook_async(
    provider: str,
    output_file: Optional[str],
    reply: str,
    req_id: str,
    caller: str,
    email_req_id: str = "",
    email_msg_id: str = "",
    email_from: str = "",
    work_dir: str = "",
    done_seen: bool = True,
    status: str = COMPLETION_STATUS_COMPLETED,
    caller_pane_id: str = "",
    caller_terminal: str = "",
) -> None:
    """Run the completion hook in a background thread."""
    if not env_bool("CCB_COMPLETION_HOOK_ENABLED", True):
        return

    def _run():
        try:
            # Find ccb-completion-hook script (Python script only, not .cmd wrapper)
            script_paths = [
                Path(__file__).parent.parent / "bin" / "ccb-completion-hook",
                Path.home() / ".local" / "bin" / "ccb-completion-hook",
                Path("/usr/local/bin/ccb-completion-hook"),
            ]
            # On Windows, check installed location (Python script, not .cmd)
            if os.name == "nt":
                localappdata = os.environ.get("LOCALAPPDATA", "")
                if localappdata:
                    # The actual Python script is in the bin folder without extension
                    script_paths.insert(0, Path(localappdata) / "codex-dual" / "bin" / "ccb-completion-hook")

            script = None
            for p in script_paths:
                if p.exists() and p.suffix not in (".cmd", ".bat"):
                    script = str(p)
                    break

            if not script:
                return

            # Use sys.executable to run the script (cross-platform, no shebang dependency)
            cmd = [
                sys.executable,
                script,
                "--provider", provider,
                "--caller", caller,
                "--req-id", req_id,
            ]
            if output_file:
                cmd.extend(["--output", output_file])

            # Set up environment with caller and email-related vars
            env = os.environ.copy()
            env["CCB_CALLER"] = caller  # Ensure caller is passed via env var
            env["CCB_DONE_SEEN"] = "1" if done_seen else "0"  # Pass completion status
            env["CCB_COMPLETION_STATUS"] = normalize_completion_status(status, done_seen=done_seen)
            if email_req_id:
                env["CCB_EMAIL_REQ_ID"] = email_req_id
            if email_msg_id:
                env["CCB_EMAIL_MSG_ID"] = email_msg_id
            if email_from:
                env["CCB_EMAIL_FROM"] = email_from
            # Pass work_dir for session file lookup
            if work_dir:
                env["CCB_WORK_DIR"] = work_dir
            if caller_pane_id:
                env["CCB_CALLER_PANE_ID"] = caller_pane_id
            if caller_terminal:
                env["CCB_CALLER_TERMINAL"] = caller_terminal

            # Pass reply via stdin to avoid command line length limits
            # Use longer timeout for SMTP retries (3 retries * 8s max backoff + send time)
            result = subprocess.run(cmd, input=(reply or "").encode("utf-8"), capture_output=True, timeout=60, env=env)
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
                if stderr:
                    print(f"[completion-hook] Error: {stderr}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print("[completion-hook] Timeout waiting for email send", file=sys.stderr)
        except Exception as e:
            print(f"[completion-hook] Error: {e}", file=sys.stderr)

    thread = threading.Thread(target=_run, daemon=False)
    thread.start()
    # Wait briefly to ensure hook starts, but don't block worker for full duration
    thread.join(timeout=2.0)


def notify_completion(
    provider: str,
    output_file: Optional[str],
    reply: str,
    req_id: str,
    done_seen: bool,
    caller: str = "claude",
    email_req_id: str = "",
    email_msg_id: str = "",
    email_from: str = "",
    work_dir: str = "",
    status: str | None = None,
    caller_pane_id: str = "",
    caller_terminal: str = "",
) -> None:
    """
    Notify the caller that a CCB delegation task has completed.

    Args:
        provider: Provider name (codex, gemini, opencode, droid)
        output_file: Path to the output file (if any)
        reply: The reply text from the provider
        req_id: The request ID
        done_seen: Whether the CCB_DONE signal was detected
        caller: Who initiated the request (claude, codex, droid, email)
        email_req_id: Email request ID (for email caller)
        email_msg_id: Original email Message-ID (for email caller)
        email_from: Original sender email address (for email caller)
        work_dir: Working directory for session file lookup
        status: Terminal status for notifications (completed/cancelled/failed/incomplete)
    """
    normalized_status = normalize_completion_status(status, done_seen=done_seen)
    _run_hook_async(
        provider,
        output_file,
        reply,
        req_id,
        caller,
        email_req_id,
        email_msg_id,
        email_from,
        work_dir,
        done_seen,
        normalized_status,
        caller_pane_id,
        caller_terminal,
    )
