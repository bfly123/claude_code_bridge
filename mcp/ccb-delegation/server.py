#!/usr/bin/env python3
"""
MCP stdio server for CCB cross-provider delegation.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "ccb-delegation", "version": "0.1.0"}

CACHE_DIR = Path(
    os.environ.get("CCB_DELEGATION_CACHE_DIR")
    or (Path.home() / ".cache" / "ccb" / "delegation")
)
LOG_PATH = CACHE_DIR / "mcp-server.log"
CACHE_TTL_S = int(os.environ.get("CCB_DELEGATION_TTL_S") or str(60 * 60 * 24))

PROVIDERS = {
    "codex": {"ask": "cask", "pend": "cpend", "ping": "cping"},
    "gemini": {"ask": "gask", "pend": "gpend", "ping": "gping"},
    "claude": {"ask": "lask", "pend": "lpend", "ping": "lping"},
    "opencode": {"ask": "oask", "pend": "opend", "ping": "oping"},
    "cursor": {"ask": "curask", "pend": "curpend", "ping": "curping"},
}

ALIAS_TOOLS = [
    ("cask", "codex", "ask"),
    ("gask", "gemini", "ask"),
    ("lask", "claude", "ask"),
    ("oask", "opencode", "ask"),
    ("curask", "cursor", "ask"),
    ("cpend", "codex", "pend"),
    ("gpend", "gemini", "pend"),
    ("lpend", "claude", "pend"),
    ("opend", "opencode", "pend"),
    ("curpend", "cursor", "pend"),
    ("cping", "codex", "ping"),
    ("gping", "gemini", "ping"),
    ("lping", "claude", "ping"),
    ("oping", "opencode", "ping"),
    ("curping", "cursor", "ping"),
]
ALIAS_MAP = {name: (provider, kind) for name, provider, kind in ALIAS_TOOLS}


def _ask_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Request text to send to the provider.",
            },
            "timeout_s": {
                "type": "number",
                "description": "Timeout in seconds for the provider request.",
                "default": 120,
            },
            "session_file": {
                "type": "string",
                "description": "Path to the provider session file (e.g., .codex-session).",
            },
        },
        "required": ["message"],
    }


def _pend_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task id returned by ccb_ask_* (optional: latest).",
            },
            "session_file": {
                "type": "string",
                "description": "Path to the provider session file (optional fallback).",
            },
        },
        "required": [],
    }


def _ping_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "session_file": {
                "type": "string",
                "description": "Path to the provider session file (optional).",
            }
        },
        "required": [],
    }


def _cursor_ask_schema() -> dict[str, Any]:
    """Cursor-specific ask schema with resume and force parameters."""
    return {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Request text to send to cursor-agent.",
            },
            "timeout_s": {
                "type": "number",
                "description": "Timeout in seconds for the cursor-agent request.",
                "default": 300,
            },
            "resume": {
                "type": "string",
                "description": "Chat ID to resume a previous session.",
            },
            "force": {
                "type": "boolean",
                "description": "Allow file editing (default: true).",
                "default": True,
            },
            "model": {
                "type": "string",
                "description": "Model to use for cursor-agent.",
            },
        },
        "required": ["message"],
    }


def _cursor_pend_schema() -> dict[str, Any]:
    """Cursor-specific pend schema."""
    return {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task id returned by curask (optional: latest).",
            },
        },
        "required": [],
    }


TOOL_DEFS = []
for provider in ("codex", "gemini", "claude", "opencode", "cursor"):
    if provider == "cursor":
        ask_schema = _cursor_ask_schema()
        pend_schema = _cursor_pend_schema()
    else:
        ask_schema = _ask_schema()
        pend_schema = _pend_schema()

    TOOL_DEFS.append(
        {
            "name": f"ccb_ask_{provider}",
            "description": f"Submit a background request to {provider} (CCB).",
            "inputSchema": ask_schema,
        }
    )
    TOOL_DEFS.append(
        {
            "name": f"ccb_pend_{provider}",
            "description": f"Fetch the result of a background {provider} request.",
            "inputSchema": pend_schema,
        }
    )
    TOOL_DEFS.append(
        {
            "name": f"ccb_ping_{provider}",
            "description": f"Check availability for {provider} in CCB.",
            "inputSchema": _ping_schema(),
        }
    )

for alias, provider, kind in ALIAS_TOOLS:
    if provider == "cursor":
        if kind == "ask":
            schema = _cursor_ask_schema()
        elif kind == "pend":
            schema = _cursor_pend_schema()
        else:
            schema = _ping_schema()
    else:
        if kind == "ask":
            schema = _ask_schema()
        elif kind == "pend":
            schema = _pend_schema()
        else:
            schema = _ping_schema()
    TOOL_DEFS.append(
        {
            "name": alias,
            "description": f"Alias for ccb_{kind}_{provider}.",
            "inputSchema": schema,
        }
    )


def _log(message: str) -> None:
    try:
        _ensure_cache()
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            fh.write(f"[{ts}] {message}\n")
    except Exception:
        pass


def _ensure_cache() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cleanup_cache() -> None:
    if CACHE_TTL_S <= 0:
        return
    now = time.time()
    try:
        _ensure_cache()
        for path in CACHE_DIR.glob("*.json"):
            try:
                if now - path.stat().st_mtime > CACHE_TTL_S:
                    base = path.stem
                    out_path = CACHE_DIR / f"{base}.out"
                    path.unlink(missing_ok=True)
                    out_path.unlink(missing_ok=True)
            except Exception:
                continue
    except Exception:
        pass


def _send(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def _rpc_result(req_id: Any, result: dict[str, Any]) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _rpc_error(req_id: Any, code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _tool_ok(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=True),
            }
        ]
    }


def _tool_error(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


def _make_task_id(provider: str) -> str:
    ts = int(time.time())
    rand = secrets.token_hex(2)
    return f"{provider}-{ts}-{rand}"


def _meta_path(task_id: str) -> Path:
    return CACHE_DIR / f"{task_id}.json"


def _output_path(task_id: str) -> Path:
    return CACHE_DIR / f"{task_id}.out"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    try:
        path.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")
    except Exception:
        pass


def _spawn_background(cmd: list[str], message: str, meta_path: Path) -> int | None:
    _ensure_cache()
    try:
        stderr_handle = LOG_PATH.open("a", encoding="utf-8")
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=stderr_handle,
            text=True,
            start_new_session=True,
        )
        try:
            stderr_handle.close()
        except Exception:
            pass
    except Exception as exc:
        _log(f"spawn failed cmd={cmd!r} err={exc}")
        return None

    try:
        if proc.stdin:
            proc.stdin.write(message)
            proc.stdin.close()
    except Exception as exc:
        _log(f"stdin failed pid={proc.pid} err={exc}")

    def _wait_and_record() -> None:
        exit_code = None
        try:
            exit_code = proc.wait()
        except Exception:
            pass
        meta = _read_json(meta_path) or {}
        meta["exit_code"] = int(exit_code) if exit_code is not None else None
        meta["finished_at"] = int(time.time())
        meta["status"] = "completed" if exit_code == 0 else "error"
        _write_json(meta_path, meta)

    thread = threading.Thread(target=_wait_and_record, daemon=True)
    thread.start()
    return proc.pid


def _resolve_provider(name: str) -> str | None:
    for provider in PROVIDERS:
        if name.endswith(provider):
            return provider
    return None


def _submit_task(provider: str, args: dict[str, Any]) -> dict[str, Any]:
    message = str(args.get("message") or "").strip()
    if not message:
        return _tool_error("message is required")

    # Default timeout: 300s for cursor, 120s for others
    default_timeout = 300.0 if provider == "cursor" else 120.0
    timeout_s = args.get("timeout_s", default_timeout)
    try:
        timeout_s = float(timeout_s)
    except Exception:
        timeout_s = default_timeout

    task_id = _make_task_id(provider)
    out_path = _output_path(task_id)
    meta_path = _meta_path(task_id)

    meta = {
        "task_id": task_id,
        "provider": provider,
        "output_file": str(out_path),
        "status": "running",
        "started_at": int(time.time()),
        "exit_code": None,
    }

    if provider == "cursor":
        # Cursor-specific command building
        resume = str(args.get("resume") or "").strip() or None
        force = args.get("force", True)
        model = str(args.get("model") or "").strip() or None

        cmd = [PROVIDERS[provider]["ask"], "--sync", "--output", str(out_path), "--timeout", str(timeout_s), "-q"]
        if resume:
            cmd.extend(["--resume", resume])
            meta["resume"] = resume
        if not force:
            cmd.append("--no-force")
        if model:
            cmd.extend(["--model", model])
            meta["model"] = model
        meta["force"] = force
    else:
        # Standard provider command building
        session_file = str(args.get("session_file") or "").strip() or None
        if session_file and not Path(session_file).expanduser().exists():
            return _tool_error(f"session_file not found: {session_file}")

        cmd = [PROVIDERS[provider]["ask"], "--sync", "--output", str(out_path), "--timeout", str(timeout_s), "-q"]
        if session_file:
            cmd.extend(["--session-file", session_file])
            meta["session_file"] = session_file

    _write_json(meta_path, meta)

    pid = _spawn_background(cmd, message, meta_path)
    if pid is None:
        return _tool_error("failed to launch provider command")

    meta["pid"] = pid
    _write_json(meta_path, meta)

    return _tool_ok(
        {
            "task_id": task_id,
            "status": "submitted",
            "output_file": str(out_path),
        }
    )


def _load_latest_meta(provider: str) -> dict[str, Any] | None:
    try:
        metas = []
        for path in CACHE_DIR.glob("*.json"):
            data = _read_json(path)
            if not data:
                continue
            if data.get("provider") != provider:
                continue
            try:
                mtime = path.stat().st_mtime
            except Exception:
                mtime = 0
            metas.append((mtime, data))
        if not metas:
            return None
        metas.sort(key=lambda item: item[0], reverse=True)
        return metas[0][1]
    except Exception:
        return None


def _pend_task(provider: str, args: dict[str, Any]) -> dict[str, Any]:
    task_id = str(args.get("task_id") or "").strip()
    session_file = str(args.get("session_file") or "").strip() or None

    meta: dict[str, Any] | None = None
    if task_id:
        meta = _read_json(_meta_path(task_id))
        if not meta:
            return _tool_error(f"unknown task_id: {task_id}")
    else:
        meta = _load_latest_meta(provider)
        if not meta:
            return _pend_fallback(provider, session_file)

    out_path = meta.get("output_file")
    reply = ""
    status = meta.get("status") or "pending"
    if out_path:
        try:
            out_text = Path(out_path).read_text(encoding="utf-8")
            reply = out_text.strip()
            if reply:
                status = "completed"
        except Exception:
            pass

    return _tool_ok(
        {
            "task_id": meta.get("task_id") or task_id,
            "status": status,
            "reply": reply,
            "output_file": out_path,
            "exit_code": meta.get("exit_code"),
        }
    )


def _pend_fallback(provider: str, session_file: str | None) -> dict[str, Any]:
    cmd = [PROVIDERS[provider]["pend"]]
    if session_file:
        cmd.extend(["--session-file", session_file])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as exc:
        return _tool_error(f"pend failed: {exc}")
    if res.returncode != 0:
        msg = res.stdout.strip() or res.stderr.strip() or "pend failed"
        return _tool_error(msg)
    return _tool_ok({"status": "completed", "reply": res.stdout.strip()})


def _ping_provider(provider: str, args: dict[str, Any]) -> dict[str, Any]:
    session_file = str(args.get("session_file") or "").strip() or None
    cmd = [PROVIDERS[provider]["ping"]]
    if session_file:
        cmd.extend(["--session-file", session_file])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as exc:
        return _tool_error(f"ping failed: {exc}")
    available = res.returncode == 0
    msg = res.stdout.strip() or res.stderr.strip()
    return _tool_ok({"available": available, "message": msg})


def _handle_tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    alias = ALIAS_MAP.get(name)
    if alias:
        provider, kind = alias
        if kind == "ask":
            return _submit_task(provider, args)
        if kind == "pend":
            return _pend_task(provider, args)
        if kind == "ping":
            return _ping_provider(provider, args)
        return _tool_error(f"unknown tool kind: {kind}")

    provider = _resolve_provider(name)
    if not provider or provider not in PROVIDERS:
        return _tool_error(f"unknown tool: {name}")
    if name.startswith("ccb_ask_"):
        return _submit_task(provider, args)
    if name.startswith("ccb_pend_"):
        return _pend_task(provider, args)
    if name.startswith("ccb_ping_"):
        return _ping_provider(provider, args)
    return _tool_error(f"unknown tool: {name}")


def _handle_request(msg: dict[str, Any]) -> None:
    method = msg.get("method")
    req_id = msg.get("id")

    if method == "initialize":
        params = msg.get("params") or {}
        proto = params.get("protocolVersion") or PROTOCOL_VERSION
        result = {
            "protocolVersion": proto,
            "capabilities": {"tools": {"list": True}},
            "serverInfo": SERVER_INFO,
        }
        _rpc_result(req_id, result)
        return

    if method == "initialized":
        return

    if method == "tools/list":
        _rpc_result(req_id, {"tools": TOOL_DEFS})
        return

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        if not name:
            _rpc_error(req_id, -32602, "missing tool name")
            return
        result = _handle_tool_call(str(name), args)
        _rpc_result(req_id, result)
        return

    if method in ("shutdown", "exit"):
        _rpc_result(req_id, {})
        raise SystemExit(0)

    if req_id is not None:
        _rpc_error(req_id, -32601, f"unknown method: {method}")


def main() -> int:
    _cleanup_cache()
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        if not isinstance(msg, dict):
            continue
        try:
            _handle_request(msg)
        except SystemExit:
            return 0
        except Exception as exc:
            _log(f"handle_request error: {exc}")
            req_id = msg.get("id")
            if req_id is not None:
                _rpc_error(req_id, -32603, "internal error")
    return 0


if __name__ == "__main__":
    sys.exit(main())
