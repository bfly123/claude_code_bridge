from __future__ import annotations

import json
import socket
import time
from pathlib import Path


def read_state(state_file: Path) -> dict | None:
    try:
        raw = state_file.read_text(encoding="utf-8")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def ping_daemon(protocol_prefix: str, timeout_s: float, state_file: Path) -> bool:
    st = read_state(state_file)
    if not st:
        return False
    try:
        host = st.get("connect_host") or st["host"]
        port = int(st["port"])
        token = st["token"]
    except Exception:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout_s) as sock:
            req = {"type": f"{protocol_prefix}.ping", "v": 1, "id": "ping", "token": token}
            sock.sendall((json.dumps(req) + "\n").encode("utf-8"))
            buf = b""
            deadline = time.time() + timeout_s
            while b"\n" not in buf and time.time() < deadline:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                buf += chunk
            if b"\n" not in buf:
                return False
            line = buf.split(b"\n", 1)[0].decode("utf-8", errors="replace")
            resp = json.loads(line)
            return resp.get("type") in (f"{protocol_prefix}.pong", f"{protocol_prefix}.response") and int(resp.get("exit_code") or 0) == 0
    except Exception:
        return False


def shutdown_daemon(protocol_prefix: str, timeout_s: float, state_file: Path) -> bool:
    st = read_state(state_file)
    if not st:
        return False
    try:
        host = st.get("connect_host") or st["host"]
        port = int(st["port"])
        token = st["token"]
    except Exception:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout_s) as sock:
            req = {"type": f"{protocol_prefix}.shutdown", "v": 1, "id": "shutdown", "token": token}
            sock.sendall((json.dumps(req) + "\n").encode("utf-8"))
            _ = sock.recv(1024)
        return True
    except Exception:
        return False
