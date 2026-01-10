from __future__ import annotations

import os
from pathlib import Path


def run_dir() -> Path:
    return Path.home() / ".cache" / "ccb"


def state_file_path(name: str) -> Path:
    if name.endswith(".json"):
        return run_dir() / name
    return run_dir() / f"{name}.json"


def log_path(name: str) -> Path:
    if name.endswith(".log"):
        return run_dir() / name
    return run_dir() / f"{name}.log"


def write_log(path: Path, msg: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(msg.rstrip() + "\n")
    except Exception:
        pass


def random_token() -> str:
    return os.urandom(16).hex()


def normalize_connect_host(host: str) -> str:
    host = (host or "").strip()
    if not host or host in ("0.0.0.0",):
        return "127.0.0.1"
    if host in ("::", "[::]"):
        return "::1"
    return host
