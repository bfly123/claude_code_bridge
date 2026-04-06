from __future__ import annotations

from pathlib import Path

from .writable import check_session_writable


def safe_write_session(session_file: Path, content: str) -> tuple[bool, str | None]:
    session_file = Path(session_file)
    writable, reason, fix = check_session_writable(session_file)
    if not writable:
        return False, f'❌ Cannot write {session_file.name}: {reason}\n💡 Fix: {fix}'

    tmp_file = session_file.with_suffix('.tmp')
    try:
        tmp_file.write_text(content, encoding='utf-8')
        __import__('os').replace(tmp_file, session_file)
        return True, None
    except PermissionError as exc:
        _cleanup_tmp_file(tmp_file)
        return False, f'❌ Cannot write {session_file.name}: {exc}\n💡 Try: rm -f {session_file} then retry'
    except Exception as exc:
        _cleanup_tmp_file(tmp_file)
        return False, f'❌ Write failed: {exc}'


def print_session_error(msg: str, to_stderr: bool = True) -> None:
    import sys

    output = sys.stderr if to_stderr else sys.stdout
    print(msg, file=output)


def _cleanup_tmp_file(tmp_file: Path) -> None:
    if not tmp_file.exists():
        return
    try:
        tmp_file.unlink()
    except Exception:
        pass


__all__ = ['print_session_error', 'safe_write_session']
