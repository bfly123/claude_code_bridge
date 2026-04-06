from __future__ import annotations

import json
import sys
from typing import Any


def send(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def rpc_result(req_id: Any, result: dict[str, Any]) -> None:
    send({"jsonrpc": "2.0", "id": req_id, "result": result})


def rpc_error(req_id: Any, code: int, message: str) -> None:
    send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def tool_ok(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=True),
            }
        ]
    }


def tool_error(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


__all__ = ['rpc_error', 'rpc_result', 'send', 'tool_error', 'tool_ok']
