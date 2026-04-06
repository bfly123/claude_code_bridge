from __future__ import annotations

import json
import time
from pathlib import Path


def read_gemini_session_id(session_path: Path) -> str:
    if not session_path or not session_path.exists():
        return ""
    for _ in range(5):
        try:
            payload = json.loads(session_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            time.sleep(0.05)
            continue
        except Exception:
            return ""
        if isinstance(payload, dict) and isinstance(payload.get("sessionId"), str):
            return payload["sessionId"]
        return ""
    return ""


__all__ = ['read_gemini_session_id']
