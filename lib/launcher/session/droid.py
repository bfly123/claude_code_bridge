from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys


def read_droid_session_metadata(project_root: Path) -> tuple[str | None, str | None]:
    droid_session_path = None
    droid_session_id = None
    try:
        module_name = "droid_comm" if "droid_comm" in sys.modules else "provider_backends.droid.comm"
        droid_comm = import_module(module_name)
        DroidLogReader = getattr(droid_comm, "DroidLogReader")
        read_droid_session_start = getattr(droid_comm, "read_droid_session_start")

        reader = DroidLogReader(work_dir=project_root)
        session_path = reader.current_session_path()
        if session_path and session_path.exists():
            droid_session_path = str(session_path)
            _cwd, session_id = read_droid_session_start(session_path)
            if session_id:
                droid_session_id = session_id
    except Exception:
        pass
    return droid_session_id, droid_session_path
