#!/usr/bin/env python3
"""
MCP stdio server for CCB agent-first delegation.
"""

from __future__ import annotations

import json
import os
import sys
from io import StringIO
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "ccb-delegation", "version": "0.2.0"}

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
LIB_DIR = PROJECT_ROOT / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from ask_cli.runtime import build_context, daemon_client, submit_agent_target, watch_job


CCB_CALLER = os.environ.get("CCB_CALLER", "droid").strip().lower() or "droid"


def _ask_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "description": "Target agent name from .ccb/ccb.config.",
            },
            "message": {
                "type": "string",
                "description": "Request text to send to the target agent.",
            },
            "wait": {
                "type": "boolean",
                "description": "Wait for a terminal reply before returning.",
                "default": False,
            },
            "timeout_s": {
                "type": "number",
                "description": "Timeout in seconds when wait=true.",
                "default": 120,
            },
            "work_dir": {
                "type": "string",
                "description": "Project work directory that contains .ccb/ccb.config.",
            },
            "task_id": {
                "type": "string",
                "description": "Optional logical task id for correlation.",
            },
            "reply_to": {
                "type": "string",
                "description": "Optional job id to use as reply_to correlation.",
            },
        },
        "required": ["agent_name", "message"],
    }


def _pend_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "A job_id or agent name to inspect.",
            },
            "work_dir": {
                "type": "string",
                "description": "Project work directory that contains .ccb/ccb.config.",
            },
        },
        "required": ["target"],
    }


def _ping_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Agent name, all, or ccbd.",
                "default": "ccbd",
            },
            "work_dir": {
                "type": "string",
                "description": "Project work directory that contains .ccb/ccb.config.",
            },
        },
        "required": [],
    }


TOOL_DEFS = [
    {
        "name": "ccb_ask_agent",
        "description": "Submit a request to a named CCB agent.",
        "inputSchema": _ask_schema(),
    },
    {
        "name": "ccb_pend_agent",
        "description": "Inspect the latest state/reply for a named agent or job.",
        "inputSchema": _pend_schema(),
    },
    {
        "name": "ccb_ping_agent",
        "description": "Check ccbd or mounted-agent health inside the current project.",
        "inputSchema": _ping_schema(),
    },
]


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


def _parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_timeout(value: Any, default: float = 120.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def _build_context_for(work_dir: str | None):
    cwd = Path(work_dir).expanduser() if work_dir else Path.cwd()
    return build_context(None, cwd=cwd)


def _submit_task(args: dict[str, Any]) -> dict[str, Any]:
    agent_name = str(args.get("agent_name") or "").strip().lower()
    message = str(args.get("message") or "").strip()
    if not agent_name:
        return _tool_error("agent_name is required")
    if not message:
        return _tool_error("message is required")

    wait = _parse_bool(args.get("wait"), default=False)
    timeout_s = _parse_timeout(args.get("timeout_s"), default=120.0)
    work_dir = str(args.get("work_dir") or "").strip() or None
    task_id = str(args.get("task_id") or "").strip() or None
    reply_to = str(args.get("reply_to") or "").strip() or None

    try:
        context = _build_context_for(work_dir)
        payload = submit_agent_target(
            context,
            target=agent_name,
            message=message,
            sender=CCB_CALLER,
            task_id=task_id,
            reply_to=reply_to,
        )
        response = {
            "job_id": payload["job_id"],
            "agent_name": payload.get("agent_name") or agent_name,
            "target_kind": payload.get("target_kind"),
            "target_name": payload.get("target_name") or agent_name,
            "status": payload.get("status"),
        }
        if wait:
            terminal = watch_job(
                context,
                payload["job_id"],
                StringIO(),
                timeout=timeout_s,
                emit_output=False,
            )
            response.update(
                {
                    "terminal": True,
                    "status": terminal.status,
                    "reply": terminal.reply or "",
                }
            )
        else:
            response.update(
                {
                    "terminal": False,
                    "reply_mode": "async",
                    "wait_hint": f"ask wait {payload['job_id']}",
                }
            )
        return _tool_ok(response)
    except Exception as exc:
        return _tool_error(str(exc))


def _pend_task(args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("target") or "").strip().lower()
    if not target:
        return _tool_error("target is required")

    work_dir = str(args.get("work_dir") or "").strip() or None
    try:
        context = _build_context_for(work_dir)
        payload = daemon_client(context).watch(target, cursor=0)
        return _tool_ok(
            {
                "job_id": payload.get("job_id"),
                "agent_name": payload.get("agent_name"),
                "target_kind": payload.get("target_kind"),
                "target_name": payload.get("target_name"),
                "status": payload.get("status"),
                "terminal": bool(payload.get("terminal")),
                "reply": payload.get("reply") or "",
                "cursor": payload.get("cursor"),
            }
        )
    except Exception as exc:
        return _tool_error(str(exc))


def _ping_agent(args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("target") or "ccbd").strip().lower() or "ccbd"
    work_dir = str(args.get("work_dir") or "").strip() or None
    try:
        context = _build_context_for(work_dir)
        payload = daemon_client(context).ping(target)
        return _tool_ok(payload)
    except Exception as exc:
        return _tool_error(str(exc))


def _handle_tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "ccb_ask_agent":
        return _submit_task(args)
    if name == "ccb_pend_agent":
        return _pend_task(args)
    if name == "ccb_ping_agent":
        return _ping_agent(args)
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
        except Exception:
            req_id = msg.get("id")
            if req_id is not None:
                _rpc_error(req_id, -32603, "internal error")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
