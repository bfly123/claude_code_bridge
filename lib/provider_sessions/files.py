"""
Provider session file pathing and write helpers.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Optional, Tuple

from project.discovery import find_nearest_project_anchor, find_workspace_binding, load_workspace_binding, project_ccb_dir


CCB_PROJECT_CONFIG_DIRNAME = ".ccb"


def project_config_dir(work_dir: Path) -> Path:
    return Path(work_dir).resolve() / CCB_PROJECT_CONFIG_DIRNAME


def resolve_project_config_dir(work_dir: Path) -> Path:
    return project_config_dir(work_dir)


def check_session_writable(session_file: Path) -> Tuple[bool, Optional[str], Optional[str]]:
    session_file = Path(session_file)
    parent = session_file.parent

    if not parent.exists():
        return False, f"Directory not found: {parent}", f"mkdir -p {parent}"

    if not os.access(parent, os.X_OK):
        return False, f"Directory not accessible (missing x permission): {parent}", f"chmod +x {parent}"

    if not os.access(parent, os.W_OK):
        return False, f"Directory not writable: {parent}", f"chmod u+w {parent}"

    if not session_file.exists():
        return True, None, None

    if session_file.is_symlink():
        target = session_file.resolve()
        return False, f"Is symlink pointing to {target}", f"rm -f {session_file}"

    if session_file.is_dir():
        return False, "Is directory, not file", f"rmdir {session_file} or rm -rf {session_file}"

    if not session_file.is_file():
        return False, "Not a regular file", f"rm -f {session_file}"

    if os.name != "nt" and hasattr(os, "getuid"):
        try:
            file_stat = session_file.stat()
            file_uid = getattr(file_stat, "st_uid", None)
            current_uid = os.getuid()

            if isinstance(file_uid, int) and file_uid != current_uid:
                import pwd

                try:
                    owner_name = pwd.getpwuid(file_uid).pw_name
                except KeyError:
                    owner_name = str(file_uid)
                current_name = pwd.getpwuid(current_uid).pw_name
                return (
                    False,
                    f"File owned by {owner_name} (current user: {current_name})",
                    f"sudo chown {current_name}:{current_name} {session_file}",
                )
        except Exception:
            pass

    if not os.access(session_file, os.W_OK):
        mode = stat.filemode(session_file.stat().st_mode)
        return False, f"File not writable (mode: {mode})", f"chmod u+w {session_file}"

    return True, None, None


def safe_write_session(session_file: Path, content: str) -> Tuple[bool, Optional[str]]:
    session_file = Path(session_file)
    writable, reason, fix = check_session_writable(session_file)
    if not writable:
        return False, f"❌ Cannot write {session_file.name}: {reason}\n💡 Fix: {fix}"

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
    import sys

    output = sys.stderr if to_stderr else sys.stdout
    print(msg, file=output)


def find_project_session_file(work_dir: Path, session_filename: str) -> Optional[Path]:
    try:
        current = Path(work_dir).resolve()
    except Exception:
        current = Path(work_dir).absolute()

    binding_path = find_workspace_binding(current)
    if binding_path is not None:
        binding = load_workspace_binding(binding_path)
        target_project = Path(str(binding['target_project'])).expanduser()
        try:
            target_project = target_project.resolve()
        except Exception:
            target_project = target_project.absolute()
        candidate = project_ccb_dir(target_project) / session_filename
        if candidate.exists():
            return candidate

    anchor = find_nearest_project_anchor(current)
    if anchor is not None:
        candidate = project_ccb_dir(anchor) / session_filename
        return candidate if candidate.exists() else None

    return None
