from __future__ import annotations

import json
import os
from pathlib import Path
import sys


def ensure_opencode_auto_config() -> None:
    try:
        config_path = Path.cwd() / "opencode.json"
        desired = {
            "permission": {
                "edit": "allow",
                "bash": "allow",
                "skill": "allow",
                "webfetch": "allow",
                "doom_loop": "allow",
                "external_directory": "allow",
            }
        }
        current: dict = {}
        if config_path.exists():
            try:
                current_raw = config_path.read_text(encoding="utf-8")
                current_obj = json.loads(current_raw)
                if isinstance(current_obj, dict):
                    current = current_obj
            except Exception:
                current = {}
        current["permission"] = dict(desired["permission"])
        tmp_path = config_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, config_path)
    except Exception as exc:
        print(f"⚠️ Failed to update OpenCode config: {exc}", file=sys.stderr)
