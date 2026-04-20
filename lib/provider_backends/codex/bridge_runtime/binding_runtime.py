from __future__ import annotations

import os
from pathlib import Path
import threading
import time

from provider_backends.codex.comm_runtime.binding import extract_session_id
from provider_backends.codex.comm_runtime.log_reader_facade import CodexLogReader
from provider_backends.codex.session import CodexProjectSession
from provider_backends.codex.session_runtime.follow_policy import should_follow_workspace_sessions

from .env import env_float, path_or_none, read_session_data, session_root, session_work_dir


class CodexBindingTracker:
    def __init__(self, runtime_dir: Path):
        self.runtime_dir = runtime_dir
        self.session_file = session_file_from_env()
        self._poll_interval = env_float("CCB_CODEX_BIND_POLL_INTERVAL", 0.5)
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self.session_file is None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="codex-binding-tracker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _loop(self) -> None:
        while self._running:
            try:
                self.refresh_once()
            except Exception:
                pass
            time.sleep(max(0.05, self._poll_interval))

    def refresh_once(self) -> bool:
        context = refresh_context(self.session_file)
        if context is None:
            return False

        log_path = current_log_path(context["data"], session_file=context["session_file"])
        if log_path is None:
            return False

        session = CodexProjectSession(session_file=self.session_file, data=context["data"])
        before = binding_snapshot(context["data"])
        session.update_codex_log_binding(log_path=str(log_path), session_id=extract_session_id(log_path))
        return before != binding_snapshot(session.data)


def session_file_from_env() -> Path | None:
    raw_session_file = str(os.environ.get("CCB_SESSION_FILE") or "").strip()
    if not raw_session_file:
        return None
    return Path(raw_session_file).expanduser()


def refresh_context(session_file: Path | None) -> dict[str, object] | None:
    if session_file is None or not session_file.is_file():
        return None
    data = read_session_data(session_file)
    if not isinstance(data, dict):
        return None
    work_dir = session_work_dir(data)
    if work_dir is None:
        return None
    return {"data": data, "work_dir": work_dir, "session_file": session_file}


def current_log_path(data: dict[str, object], *, session_file: Path | None) -> Path | None:
    work_dir = session_work_dir(data)
    log_reader = CodexLogReader(
        root=session_root(data),
        log_path=path_or_none(data.get("codex_session_path")),
        session_id_filter=str(data.get("codex_session_id") or "").strip() or None,
        work_dir=work_dir,
        follow_workspace_sessions=should_follow_workspace_sessions(
            work_dir=work_dir,
            session_file=session_file,
            session_data=data,
        ),
    )
    log_path = log_reader.current_log_path()
    if log_path is None or not log_path.is_file():
        return None
    return log_path


def binding_snapshot(data: dict[str, object]) -> tuple[str, str, str, str]:
    return (
        str(data.get("codex_session_path") or "").strip(),
        str(data.get("codex_session_id") or "").strip(),
        str(data.get("codex_start_cmd") or "").strip(),
        str(data.get("start_cmd") or "").strip(),
    )


__all__ = ["CodexBindingTracker"]
