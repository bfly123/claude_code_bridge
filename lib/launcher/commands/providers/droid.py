from __future__ import annotations

import os
from pathlib import Path
import sys
from importlib import import_module


def get_latest_droid_session_id(factory) -> tuple[str | None, bool, Path | None]:
    try:
        module_name = "droid_comm" if "droid_comm" in sys.modules else "provider_backends.droid.comm"
        droid_comm = import_module(module_name)
        DroidLogReader = getattr(droid_comm, "DroidLogReader")
        read_droid_session_start = getattr(droid_comm, "read_droid_session_start")
    except Exception:
        return None, False, None

    reader = DroidLogReader(work_dir=factory.project_root)
    session_path = reader.current_session_path()
    if not session_path or not session_path.exists():
        return None, False, None

    cwd, session_id = read_droid_session_start(session_path)
    resume_dir = None
    if isinstance(cwd, str) and cwd.strip():
        try:
            candidate = Path(cwd)
            if candidate.is_dir():
                resume_dir = candidate
        except Exception:
            resume_dir = None
    return session_id or None, True, resume_dir


def build_droid_start_cmd(factory) -> str:
    cmd = (os.environ.get("DROID_START_CMD") or "droid").strip() or "droid"
    resume_cmd = (os.environ.get("DROID_RESUME_CMD") or "").strip()
    if factory.resume:
        session_id, has_history, resume_dir = factory.get_latest_droid_session_id()
        if has_history:
            if resume_cmd:
                cmd = resume_cmd
            else:
                if resume_dir:
                    cmd = f"{factory.build_cd_cmd_fn(resume_dir)}{cmd}"
                cmd = f"{cmd} -r"
            sid_hint = session_id[:8] if session_id else ""
            print(f"🔁 {factory.translate_fn('resuming_session', provider='Droid', session_id=sid_hint)}")
        else:
            print(f"ℹ️ {factory.translate_fn('no_history_fresh', provider='Droid')}")
    return cmd
