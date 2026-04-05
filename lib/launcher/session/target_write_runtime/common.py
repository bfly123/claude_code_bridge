from __future__ import annotations

import sys
from pathlib import Path


def ensure_session_writable(store, session_file: Path) -> bool:
    writable, reason, fix = store.check_session_writable_fn(session_file)
    if writable:
        return True
    print(f"❌ Cannot write {session_file.name}: {reason}", file=sys.stderr)
    print(f"💡 Fix: {fix}", file=sys.stderr)
    return False


def write_payload(store, session_file: Path, payload: str) -> bool:
    ok, err = store.safe_write_session_fn(session_file, payload)
    if ok:
        return True
    if err:
        print(err, file=sys.stderr)
    return False
