from __future__ import annotations

import errno
import os
from pathlib import Path

if not hasattr(os, 'WNOHANG'):
    os.WNOHANG = 1


def try_acquire_keeper_lock(path: Path):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = target.open('a+', encoding='utf-8')
    try:
        import fcntl  # type: ignore

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ModuleNotFoundError:
        return handle
    except OSError as exc:
        handle.close()
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            return None
        raise
    return handle


def reap_child_processes(*, waitpid_fn=os.waitpid, os_module=os) -> tuple[int, ...]:
    reaped: list[int] = []
    while True:
        try:
            pid, _status = waitpid_fn(-1, os_module.WNOHANG)
        except ChildProcessError:
            break
        except OSError as exc:
            if exc.errno in {errno.ECHILD, errno.EINTR}:
                break
            break
        if pid <= 0:
            break
        reaped.append(int(pid))
    return tuple(reaped)


__all__ = ['reap_child_processes', 'try_acquire_keeper_lock']
