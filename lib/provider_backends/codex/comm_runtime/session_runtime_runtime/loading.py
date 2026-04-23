from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable


def load_codex_session_info(*, session_finder: Callable[[], Path | None]):
    env_info = _load_env_session_info(session_finder=session_finder)
    if env_info is not None:
        return env_info
    return _load_project_session_info(session_finder=session_finder)


def _load_env_session_info(*, session_finder: Callable[[], Path | None]):
    if "CCB_SESSION_ID" not in os.environ:
        return None
    result = {
        "ccb_session_id": os.environ["CCB_SESSION_ID"],
        "runtime_dir": os.environ["CODEX_RUNTIME_DIR"],
        "input_fifo": os.environ["CODEX_INPUT_FIFO"],
        "output_fifo": os.environ.get("CODEX_OUTPUT_FIFO", ""),
        "terminal": os.environ.get("CODEX_TERMINAL", "tmux"),
        "tmux_session": os.environ.get("CODEX_TMUX_SESSION", ""),
        "pane_id": os.environ.get("CODEX_TMUX_SESSION", ""),
        "_session_file": None,
    }
    session_file = session_finder()
    return _merge_project_binding(result, session_file=session_file)


def _load_project_session_info(*, session_finder: Callable[[], Path | None]):
    project_session = session_finder()
    if project_session is None:
        return None
    data = _load_session_file(project_session)
    if data is None or not data.get("active", False):
        return None

    runtime_dir = Path(data.get("runtime_dir", ""))
    if not runtime_dir.exists():
        return None

    data["_session_file"] = str(project_session)
    return _merge_runtime_binding(data)


def _merge_project_binding(result: dict[str, object], *, session_file: Path | None):
    if session_file is None:
        return _merge_runtime_binding(result)
    file_data = _load_session_file(session_file)
    if file_data is None:
        return _merge_runtime_binding(result)
    result["codex_session_path"] = file_data.get("codex_session_path")
    result["codex_session_id"] = file_data.get("codex_session_id")
    if "job_id" in file_data:
        result["job_id"] = file_data.get("job_id")
    if "runtime_pid" in file_data:
        result["runtime_pid"] = file_data.get("runtime_pid")
    if "job_owner_pid" in file_data:
        result["job_owner_pid"] = file_data.get("job_owner_pid")
    result["_session_file"] = str(session_file)
    return _merge_runtime_binding(result)


def _load_session_file(session_file: Path) -> dict | None:
    try:
        with open(session_file, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _merge_runtime_binding(result: dict[str, object]) -> dict[str, object]:
    runtime_dir = str(result.get("runtime_dir") or "").strip()
    if not runtime_dir:
        return result
    runtime_path = Path(runtime_dir)
    if not str(result.get("job_id") or "").strip():
        job_id = _load_runtime_job_id(runtime_path)
        if job_id:
            result["job_id"] = job_id
    if _coerce_pid(result.get("job_owner_pid")) is None:
        job_owner_pid = _load_runtime_job_owner_pid(runtime_path)
        if job_owner_pid is not None:
            result["job_owner_pid"] = job_owner_pid
    return result


def _load_runtime_job_id(runtime_dir: Path) -> str | None:
    job_path = runtime_dir / "job.id"
    try:
        text = job_path.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return text or None


def _load_runtime_job_owner_pid(runtime_dir: Path) -> int | None:
    for path in (
        runtime_dir / "job-owner.pid",
        runtime_dir / "owner.pid",
        runtime_dir / "bridge.pid",
    ):
        pid = _load_runtime_pid(path)
        if pid is not None:
            return pid
    return None


def _load_runtime_pid(path: Path) -> int | None:
    try:
        return _coerce_pid(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _coerce_pid(value: object) -> int | None:
    text = str(value or "").strip()
    if not text.isdigit():
        return None
    pid = int(text)
    return pid if pid > 0 else None


__all__ = ["load_codex_session_info"]
