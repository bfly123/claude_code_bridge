from __future__ import annotations

import os
from pathlib import Path

from .debug import debug_log_reader
from .pathing import extract_cwd_from_log


def follow_workspace_sessions(reader) -> bool:
    return bool(getattr(reader, "_follow_workspace_sessions", False) and getattr(reader, "_work_dir", None))


def iter_lines_reverse(reader, log_path: Path, *, max_bytes: int, max_lines: int) -> list[str]:
    if max_bytes <= 0 or max_lines <= 0:
        return []

    try:
        with log_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            position = handle.tell()
            bytes_read = 0
            lines: list[str] = []
            buffer = b""

            while position > 0 and bytes_read < max_bytes and len(lines) < max_lines:
                remaining = max_bytes - bytes_read
                read_size = min(8192, position, remaining)
                position -= read_size
                handle.seek(position, os.SEEK_SET)
                chunk = handle.read(read_size)
                bytes_read += len(chunk)
                buffer = chunk + buffer

                parts = buffer.split(b"\n")
                buffer = parts[0]
                for part in reversed(parts[1:]):
                    if len(lines) >= max_lines:
                        break
                    text = part.decode("utf-8", errors="ignore").strip()
                    if text:
                        lines.append(text)

            if position == 0 and buffer and len(lines) < max_lines:
                text = buffer.decode("utf-8", errors="ignore").strip()
                if text:
                    lines.append(text)

            return lines
    except OSError as exc:
        debug_log_reader(f"Failed reading log tail: {log_path} ({exc})")
        return []


def scan_latest(reader) -> Path | None:
    if not reader.root.exists():
        return None
    follow_workspace = follow_workspace_sessions(reader)
    try:
        latest: Path | None = None
        latest_mtime = -1.0
        for path in (path for path in reader.root.glob("**/*.jsonl") if path.is_file()):
            if reader._session_id_filter and not follow_workspace:
                try:
                    if str(reader._session_id_filter).lower() not in str(path).lower():
                        continue
                except Exception:
                    pass
            if reader._work_dir:
                cwd = extract_cwd_from_log(reader, path)
                if not cwd or cwd != reader._work_dir:
                    continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime >= latest_mtime:
                latest = path
                latest_mtime = mtime
    except OSError:
        return None

    return latest


def latest_log(reader) -> Path | None:
    preferred = reader._preferred_log
    if preferred and preferred.exists():
        if reader._session_id_filter and not follow_workspace_sessions(reader):
            debug_log_reader(f"Using preferred log (bound): {preferred}")
            return preferred

        latest = scan_latest(reader)
        if latest and latest != preferred:
            try:
                preferred_mtime = preferred.stat().st_mtime
                latest_mtime = latest.stat().st_mtime
                if latest_mtime > preferred_mtime:
                    reader._preferred_log = latest
                    debug_log_reader(f"Preferred log stale; switching to latest: {latest}")
                    return latest
            except OSError:
                reader._preferred_log = latest
                debug_log_reader(f"Preferred log stat failed; switching to latest: {latest}")
                return latest
        debug_log_reader(f"Using preferred log: {preferred}")
        return preferred

    debug_log_reader("No valid preferred log, scanning...")
    latest = scan_latest(reader)
    if latest:
        reader._preferred_log = latest
        debug_log_reader(f"Scan found: {latest}")
        return latest
    return None


__all__ = ["follow_workspace_sessions", "iter_lines_reverse", "latest_log", "scan_latest"]
