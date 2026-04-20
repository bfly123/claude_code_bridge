from __future__ import annotations

from typing import Any


def ask_schema() -> dict[str, Any]:
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


def pend_schema() -> dict[str, Any]:
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


def ping_schema() -> dict[str, Any]:
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
        "inputSchema": ask_schema(),
    },
    {
        "name": "ccb_pend_agent",
        "description": "Inspect the latest state/reply for a named agent or job.",
        "inputSchema": pend_schema(),
    },
    {
        "name": "ccb_ping_agent",
        "description": "Check ccbd or mounted-agent health inside the current project.",
        "inputSchema": ping_schema(),
    },
]


__all__ = ['TOOL_DEFS']
