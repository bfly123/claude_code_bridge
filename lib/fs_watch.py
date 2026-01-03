from __future__ import annotations

import errno
import os
import select
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class InotifyEvent:
    wd: int
    mask: int
    cookie: int
    name: str


class _InotifyBackend:
    def add_watch(self, path: str, mask: int) -> int: ...
    def rm_watch(self, wd: int) -> None: ...
    def read(self, timeout_ms: int) -> List[InotifyEvent]: ...
    def close(self) -> None: ...


class _CtypesInotifyBackend(_InotifyBackend):
    """
    Minimal inotify implementation (no external deps).

    Uses `inotify_init1` + `inotify_add_watch`, reads events from the fd and parses linux/inotify.h layout.
    """

    def __init__(self):
        import ctypes

        self._ctypes = ctypes
        self._libc = ctypes.CDLL("libc.so.6", use_errno=True)

        init1 = getattr(self._libc, "inotify_init1", None)
        if init1 is None:
            init = getattr(self._libc, "inotify_init", None)
            if init is None:
                raise OSError("inotify not available")
            init.restype = ctypes.c_int
            fd = init()
        else:
            init1.restype = ctypes.c_int
            fd = init1(os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0))

        if fd < 0:
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err))
        self._fd = fd

        add = self._libc.inotify_add_watch
        add.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        add.restype = ctypes.c_int
        self._add = add

        rm = self._libc.inotify_rm_watch
        rm.argtypes = [ctypes.c_int, ctypes.c_int]
        rm.restype = ctypes.c_int
        self._rm = rm

    def add_watch(self, path: str, mask: int) -> int:
        encoded = os.fsencode(path)
        wd = int(self._add(self._fd, encoded, mask))
        if wd < 0:
            err = self._ctypes.get_errno()
            raise OSError(err, os.strerror(err), path)
        return wd

    def rm_watch(self, wd: int) -> None:
        if wd <= 0:
            return
        rc = int(self._rm(self._fd, int(wd)))
        if rc < 0:
            err = self._ctypes.get_errno()
            # Ignore "no such watch" / already removed.
            if err in (errno.EINVAL, errno.ENOENT):
                return
            raise OSError(err, os.strerror(err))

    def read(self, timeout_ms: int) -> List[InotifyEvent]:
        timeout_s = max(0.0, timeout_ms / 1000.0)
        try:
            r, _, _ = select.select([self._fd], [], [], timeout_s)
        except (OSError, ValueError):
            return []
        if not r:
            return []

        events: List[InotifyEvent] = []
        try:
            # Read a reasonably large chunk to drain bursts.
            data = os.read(self._fd, 64 * 1024)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return []
            raise

        offset = 0
        header_size = struct.calcsize("iIII")
        while offset + header_size <= len(data):
            wd, mask, cookie, name_len = struct.unpack_from("iIII", data, offset)
            offset += header_size
            name = ""
            if name_len:
                raw_name = data[offset : offset + name_len]
                offset += name_len
                name = raw_name.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
            events.append(InotifyEvent(wd=int(wd), mask=int(mask), cookie=int(cookie), name=name))
        return events

    def close(self) -> None:
        try:
            os.close(self._fd)
        except Exception:
            pass


class _InotifySimpleBackend(_InotifyBackend):
    def __init__(self):
        from inotify_simple import INotify  # type: ignore

        self._impl = INotify()

    def add_watch(self, path: str, mask: int) -> int:
        return int(self._impl.add_watch(path, mask))

    def rm_watch(self, wd: int) -> None:
        try:
            self._impl.rm_watch(wd)
        except Exception:
            pass

    def read(self, timeout_ms: int) -> List[InotifyEvent]:
        out: List[InotifyEvent] = []
        try:
            for ev in self._impl.read(timeout=timeout_ms):
                out.append(InotifyEvent(wd=int(ev.wd), mask=int(ev.mask), cookie=int(ev.cookie), name=str(ev.name or "")))
        except Exception:
            return []
        return out

    def close(self) -> None:
        try:
            self._impl.close()
        except Exception:
            pass


class InotifyWaiter:
    """
    Waits for changes on watched files/dirs.

    This is intentionally "dumb": it only signals "something changed" and leaves re-read/rescan
    decisions to the caller.
    """

    # linux/inotify.h masks (subset)
    MASK_MODIFY = 0x00000002
    MASK_ATTRIB = 0x00000004
    MASK_CLOSE_WRITE = 0x00000008
    MASK_MOVED_TO = 0x00000080
    MASK_CREATE = 0x00000100
    MASK_DELETE = 0x00000200
    MASK_MOVE_SELF = 0x00000800
    MASK_DELETE_SELF = 0x00000400
    MASK_Q_OVERFLOW = 0x00004000

    _FILE_MASK = MASK_MODIFY | MASK_ATTRIB | MASK_CLOSE_WRITE | MASK_MOVE_SELF | MASK_DELETE_SELF
    _DIR_MASK = MASK_MOVED_TO | MASK_CREATE | MASK_DELETE | MASK_CLOSE_WRITE | MASK_ATTRIB

    def __init__(self, *, backend: Optional[_InotifyBackend] = None):
        self._backend = backend or self._make_backend()
        self._wds: Dict[int, Tuple[str, str]] = {}  # wd -> (kind, path)
        self._tracked_files: Dict[str, str] = {}  # file path -> parent dir
        self.overflowed = False

    @staticmethod
    def _make_backend() -> _InotifyBackend:
        try:
            return _InotifySimpleBackend()
        except Exception:
            return _CtypesInotifyBackend()

    def close(self) -> None:
        for wd in list(self._wds.keys()):
            try:
                self._backend.rm_watch(wd)
            except Exception:
                pass
        self._wds.clear()
        try:
            self._backend.close()
        except Exception:
            pass

    def watch_paths(self, paths: Iterable[Path]) -> None:
        self._reset_watches()
        for path in paths:
            self._watch_one(Path(path))

    def _reset_watches(self) -> None:
        for wd in list(self._wds.keys()):
            try:
                self._backend.rm_watch(wd)
            except Exception:
                pass
        self._wds.clear()
        self._tracked_files.clear()

    def _watch_one(self, path: Path) -> None:
        path = Path(path)
        parent = str(path.parent)
        file_path = str(path)
        self._tracked_files[file_path] = parent

        try:
            exists = path.exists()
        except Exception:
            exists = False

        # If the path itself is a directory, watch it directly for new/updated files within.
        if exists:
            try:
                if path.is_dir():
                    wd_dir = self._backend.add_watch(file_path, self._DIR_MASK)
                    self._wds[wd_dir] = ("dir", file_path)
                    return
            except Exception:
                pass

        # Otherwise watch parent directory to detect replacements/rotations.
        try:
            wd_dir = self._backend.add_watch(parent, self._DIR_MASK)
            self._wds[wd_dir] = ("dir", parent)
        except Exception:
            # Directory watch might fail on some mounts; continue best-effort.
            pass

        # Watch file itself for append/modify.
        try:
            if exists:
                wd_file = self._backend.add_watch(file_path, self._FILE_MASK)
                self._wds[wd_file] = ("file", file_path)
        except Exception:
            pass

    def _refresh_file_watch(self, file_path: str) -> None:
        try:
            if not Path(file_path).exists():
                return
        except Exception:
            return

        # Remove any existing watches for this file, then re-add.
        for wd, (kind, watched_path) in list(self._wds.items()):
            if kind == "file" and watched_path == file_path:
                try:
                    self._backend.rm_watch(wd)
                except Exception:
                    pass
                self._wds.pop(wd, None)
        try:
            wd_file = self._backend.add_watch(file_path, self._FILE_MASK)
            self._wds[wd_file] = ("file", file_path)
        except Exception:
            pass

    def wait(self, timeout: float) -> bool:
        timeout_ms = int(max(0.0, timeout) * 1000)
        events = self._backend.read(timeout_ms)
        if not events:
            return False

        for ev in events:
            if ev.mask & self.MASK_Q_OVERFLOW:
                self.overflowed = True
                return True

            # If a watched file is replaced/rotated, its watch is dropped; refresh.
            if ev.mask & (self.MASK_MOVE_SELF | self.MASK_DELETE_SELF):
                kind_path = self._wds.get(ev.wd)
                if kind_path and kind_path[0] == "file":
                    self._refresh_file_watch(kind_path[1])
                return True

            # Directory event: if it targets one of our files, refresh its file watch.
            if ev.name:
                watched = self._wds.get(ev.wd)
                watched_path = watched[1] if watched else ""
                for file_path, parent in self._tracked_files.items():
                    if not parent:
                        continue
                    if watched_path and watched_path != parent:
                        continue
                    if Path(file_path).name == ev.name:
                        self._refresh_file_watch(file_path)
                        return True
                return True

        return True


class AdaptivePollWaiter:
    def __init__(self, *, base_interval: float, max_interval: float = 0.5):
        self._base = max(0.0, base_interval)
        self._max = max(self._base, max_interval)
        self._current = self._base

    def reset(self) -> None:
        self._current = self._base

    def wait(self, timeout: float) -> bool:
        sleep_for = min(max(0.0, timeout), self._current)
        time.sleep(sleep_for)
        if timeout > 0:
            self._current = min(self._max, max(self._base, self._current * 1.5))
        return False


class FileChangeWaiter:
    """
    High-level wait primitive for "something changed on disk".

    - If `enabled` and Linux: uses inotify (low latency, low CPU).
    - Otherwise: adaptive polling sleep (safe fallback).
    """

    def __init__(
        self,
        paths: Iterable[Path],
        *,
        enabled: bool,
        poll_interval: float = 0.05,
        debug_name: str = "",
    ):
        self._paths = [Path(p) for p in paths if p]
        self._enabled = bool(enabled)
        self._debug_name = debug_name
        self._poll = AdaptivePollWaiter(base_interval=poll_interval)
        self._inotify: Optional[InotifyWaiter] = None
        self._use_inotify = False

        self._maybe_enable_inotify()
        self.update_paths(self._paths)

    def close(self) -> None:
        if self._inotify:
            try:
                self._inotify.close()
            except Exception:
                pass
        self._inotify = None

    def _maybe_enable_inotify(self) -> None:
        if not self._enabled:
            return
        if sys.platform != "linux":
            return
        try:
            self._inotify = InotifyWaiter()
            self._use_inotify = True
        except Exception:
            self._inotify = None
            self._use_inotify = False

    @property
    def overflowed(self) -> bool:
        return bool(self._inotify and self._inotify.overflowed)

    def reset_backoff(self) -> None:
        self._poll.reset()

    def update_paths(self, paths: Iterable[Path]) -> None:
        self._paths = [Path(p) for p in paths if p]
        if self._use_inotify and self._inotify:
            try:
                self._inotify.watch_paths(self._paths)
            except Exception:
                # Inotify can be unreliable on some mounts; fall back to polling.
                self._use_inotify = False
                try:
                    self._inotify.close()
                except Exception:
                    pass
                self._inotify = None

    def wait(self, timeout: float) -> bool:
        if self._use_inotify and self._inotify:
            try:
                return bool(self._inotify.wait(timeout))
            except Exception:
                # Degrade to polling on unexpected failures.
                self._use_inotify = False
                try:
                    self._inotify.close()
                except Exception:
                    pass
                self._inotify = None
        return bool(self._poll.wait(timeout))
