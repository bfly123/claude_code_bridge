#!/usr/bin/env python3
"""
MCP stdio server for CCB agent-first delegation.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "ccb-delegation", "version": "0.2.0"}

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
LIB_DIR = PROJECT_ROOT / "lib"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from server_runtime_io import rpc_error, rpc_result
from server_runtime_protocol import handle_request
from server_runtime_schema import TOOL_DEFS
from server_runtime_tools import handle_tool_call


CCB_CALLER = os.environ.get("CCB_CALLER", "droid").strip().lower() or "droid"


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
            handle_request(
                msg,
                protocol_version=PROTOCOL_VERSION,
                server_info=SERVER_INFO,
                tool_defs=TOOL_DEFS,
                tool_handler=lambda name, args: handle_tool_call(name, args, caller=CCB_CALLER),
                rpc_result=rpc_result,
                rpc_error=rpc_error,
            )
        except SystemExit:
            return 0
        except Exception:
            req_id = msg.get("id")
            if req_id is not None:
                _rpc_error(req_id, -32603, "internal error")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
