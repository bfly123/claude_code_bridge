from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def write_project_session(project_file: Path, data: dict[str, Any]) -> None:
    tmp_file = project_file.with_suffix(".tmp")
    try:
        with tmp_file.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_file, project_file)
    except PermissionError as exc:
        print(f"⚠️  Cannot update {project_file.name}: {exc}", file=sys.stderr)
        print(f"💡 Try: sudo chown $USER:$USER {project_file}", file=sys.stderr)
        if tmp_file.exists():
            tmp_file.unlink(missing_ok=True)
    except Exception as exc:
        print(f"⚠️  Failed to update {project_file.name}: {exc}", file=sys.stderr)
        if tmp_file.exists():
            tmp_file.unlink(missing_ok=True)


__all__ = ["write_project_session"]
