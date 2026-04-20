from __future__ import annotations

from typing import Any


def handle_request(
    msg: dict[str, Any],
    *,
    protocol_version: str,
    server_info: dict[str, Any],
    tool_defs: list[dict[str, Any]],
    tool_handler,
    rpc_result,
    rpc_error,
) -> None:
    method = msg.get("method")
    req_id = msg.get("id")

    if method == "initialize":
        params = msg.get("params") or {}
        proto = params.get("protocolVersion") or protocol_version
        rpc_result(
            req_id,
            {
                "protocolVersion": proto,
                "capabilities": {"tools": {"list": True}},
                "serverInfo": server_info,
            },
        )
        return

    if method == "initialized":
        return

    if method == "tools/list":
        rpc_result(req_id, {"tools": tool_defs})
        return

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        if not name:
            rpc_error(req_id, -32602, "missing tool name")
            return
        rpc_result(req_id, tool_handler(str(name), args))
        return

    if method in ("shutdown", "exit"):
        rpc_result(req_id, {})
        raise SystemExit(0)

    if req_id is not None:
        rpc_error(req_id, -32601, f"unknown method: {method}")


__all__ = ['handle_request']
