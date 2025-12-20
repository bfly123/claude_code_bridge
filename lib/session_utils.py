#!/usr/bin/env python3
"""
session_utils.py - Session file permission check utility
"""
from __future__ import annotations
import os
import stat
from pathlib import Path
from typing import Tuple, Optional


def check_session_writable(session_file: Path) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if session file is writable

    Returns:
        (writable, error_reason, fix_suggestion)
    """
    session_file = Path(session_file)
    parent = session_file.parent

    # 1. Check if parent directory exists and is accessible
    if not parent.exists():
        return False, f"Directory not found: {parent}", f"mkdir -p {parent}"

    if not os.access(parent, os.X_OK):
        return False, f"Directory not accessible (missing x permission): {parent}", f"chmod +x {parent}"

    # 2. Check if parent directory is writable
    if not os.access(parent, os.W_OK):
        return False, f"Directory not writable: {parent}", f"chmod u+w {parent}"

    # 3. If file doesn't exist, directory writable is enough
    if not session_file.exists():
        return True, None, None

    # 4. Check if it's a regular file
    if session_file.is_symlink():
        target = session_file.resolve()
        return False, f"Is symlink pointing to {target}", f"rm -f {session_file}"

    if session_file.is_dir():
        return False, "Is directory, not file", f"rmdir {session_file} or rm -rf {session_file}"

    if not session_file.is_file():
        return False, "Not a regular file", f"rm -f {session_file}"

    # 5. Check file ownership
    try:
        file_stat = session_file.stat()
        file_uid = file_stat.st_uid
        current_uid = os.getuid()

        if file_uid != current_uid:
            import pwd
            try:
                owner_name = pwd.getpwuid(file_uid).pw_name
            except KeyError:
                owner_name = str(file_uid)
            current_name = pwd.getpwuid(current_uid).pw_name
            return False, f"File owned by {owner_name} (current user: {current_name})", \
                   f"sudo chown {current_name}:{current_name} {session_file}"
    except Exception:
        pass

    # 6. Check if file is writable
    if not os.access(session_file, os.W_OK):
        mode = stat.filemode(session_file.stat().st_mode)
        return False, f"File not writable (mode: {mode})", f"chmod u+w {session_file}"

    return True, None, None


def safe_write_session(session_file: Path, content: str) -> Tuple[bool, Optional[str]]:
    """
    Safely write session file, return friendly error on failure

    Returns:
        (success, error_message)
    """
    session_file = Path(session_file)

    # Pre-check
    writable, reason, fix = check_session_writable(session_file)
    if not writable:
        return False, f"❌ Cannot write {session_file.name}: {reason}\n💡 Fix: {fix}"

    # Attempt atomic write
    tmp_file = session_file.with_suffix(".tmp")
    try:
        tmp_file.write_text(content, encoding="utf-8")
        os.replace(tmp_file, session_file)
        return True, None
    except PermissionError as e:
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except Exception:
                pass
        return False, f"❌ Cannot write {session_file.name}: {e}\n💡 Try: rm -f {session_file} then retry"
    except Exception as e:
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except Exception:
                pass
        return False, f"❌ Write failed: {e}"


def print_session_error(msg: str, to_stderr: bool = True) -> None:
    """Output session-related error"""
    import sys
    output = sys.stderr if to_stderr else sys.stdout
    print(msg, file=output)
