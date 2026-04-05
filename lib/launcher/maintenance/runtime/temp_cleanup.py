from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import time

from env_utils import env_bool, env_float


def cleanup_tmpclaude_artifacts() -> int:
    if not env_bool("CCB_TMPCLAUDE_CLEAN", True):
        return 0

    patterns_raw = (os.environ.get("CCB_TMPCLAUDE_PATTERNS") or "").strip()
    patterns = [part.strip() for part in patterns_raw.split(",") if part.strip()] if patterns_raw else ["tmpclaude-*-cwd"]
    min_age_s = max(0.0, float(env_float("CCB_TMPCLAUDE_MIN_AGE_S", 300.0)))

    dirs: list[Path] = []
    if env_bool("CCB_TMPCLAUDE_CLEAN_CWD", True):
        dirs.append(Path.cwd())
    try:
        dirs.append(Path(tempfile.gettempdir()))
    except Exception:
        pass

    extra = (os.environ.get("CCB_TMPCLAUDE_DIRS") or "").strip()
    if extra:
        for part in extra.split(os.pathsep):
            candidate = part.strip()
            if not candidate:
                continue
            try:
                dirs.append(Path(candidate).expanduser())
            except Exception:
                continue

    seen_dirs: set[str] = set()
    unique_dirs: list[Path] = []
    for item in dirs:
        key = str(item)
        if key in seen_dirs:
            continue
        seen_dirs.add(key)
        unique_dirs.append(item)

    now = time.time()
    removed = 0
    for base in unique_dirs:
        try:
            if not base.exists() or not base.is_dir():
                continue
        except Exception:
            continue
        for pattern in patterns:
            try:
                candidates = list(base.glob(pattern))
            except Exception:
                candidates = []
            for path in candidates:
                try:
                    stat = path.stat()
                    if min_age_s and (now - float(stat.st_mtime)) < min_age_s:
                        continue
                    if path.is_dir():
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        path.unlink(missing_ok=True)
                    removed += 1
                except Exception:
                    continue
    return removed
