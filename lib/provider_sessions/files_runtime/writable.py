from __future__ import annotations

import os
import stat
from pathlib import Path


def check_session_writable(session_file: Path) -> tuple[bool, str | None, str | None]:
    session_file = Path(session_file)
    parent = session_file.parent

    exists, reason, fix = _check_parent_directory(parent)
    if not exists:
        return False, reason, fix

    if not session_file.exists():
        return True, None, None

    valid, reason, fix = _check_existing_session_target(session_file)
    if not valid:
        return False, reason, fix

    ownership_ok, reason, fix = _check_session_file_ownership(session_file)
    if not ownership_ok:
        return False, reason, fix

    if not os.access(session_file, os.W_OK):
        mode = stat.filemode(session_file.stat().st_mode)
        return False, f'File not writable (mode: {mode})', f'chmod u+w {session_file}'

    return True, None, None


def _check_parent_directory(parent: Path) -> tuple[bool, str | None, str | None]:
    if not parent.exists():
        return False, f'Directory not found: {parent}', f'mkdir -p {parent}'

    if not os.access(parent, os.X_OK):
        return False, f'Directory not accessible (missing x permission): {parent}', f'chmod +x {parent}'

    if not os.access(parent, os.W_OK):
        return False, f'Directory not writable: {parent}', f'chmod u+w {parent}'

    return True, None, None


def _check_existing_session_target(session_file: Path) -> tuple[bool, str | None, str | None]:
    if session_file.is_symlink():
        target = session_file.resolve()
        return False, f'Is symlink pointing to {target}', f'rm -f {session_file}'

    if session_file.is_dir():
        return False, 'Is directory, not file', f'rmdir {session_file} or rm -rf {session_file}'

    if not session_file.is_file():
        return False, 'Not a regular file', f'rm -f {session_file}'

    return True, None, None


def _check_session_file_ownership(session_file: Path) -> tuple[bool, str | None, str | None]:
    if os.name == 'nt' or not hasattr(os, 'getuid'):
        return True, None, None
    try:
        file_stat = session_file.stat()
        file_uid = getattr(file_stat, 'st_uid', None)
        current_uid = os.getuid()
        if not isinstance(file_uid, int) or file_uid == current_uid:
            return True, None, None

        import pwd

        try:
            owner_name = pwd.getpwuid(file_uid).pw_name
        except KeyError:
            owner_name = str(file_uid)
        current_name = pwd.getpwuid(current_uid).pw_name
        return (
            False,
            f'File owned by {owner_name} (current user: {current_name})',
            f'sudo chown {current_name}:{current_name} {session_file}',
        )
    except Exception:
        return True, None, None


__all__ = ['check_session_writable']
