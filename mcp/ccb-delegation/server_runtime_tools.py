from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from cli.context import CliContextBuilder
from cli.models import ParsedAskCommand, ParsedPendCommand, ParsedPingCommand
from cli.services.ask import submit_ask, watch_ask_job
from cli.services.pend import pend_target
from cli.services.ping import ping_target

from server_runtime_io import tool_error, tool_ok


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_timeout(value: Any, default: float = 120.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def build_context_for(work_dir: str | None):
    cwd = Path(work_dir).expanduser() if work_dir else Path.cwd()
    command = ParsedPingCommand(project=None, target='ccbd')
    return CliContextBuilder().build(command, cwd=cwd, bootstrap_if_missing=True)


def submit_task(args: dict[str, Any], *, caller: str) -> dict[str, Any]:
    agent_name = str(args.get("agent_name") or "").strip().lower()
    message = str(args.get("message") or "").strip()
    if not agent_name:
        return tool_error("agent_name is required")
    if not message:
        return tool_error("message is required")

    wait = parse_bool(args.get("wait"), default=False)
    timeout_s = parse_timeout(args.get("timeout_s"), default=120.0)
    work_dir = str(args.get("work_dir") or "").strip() or None
    task_id = str(args.get("task_id") or "").strip() or None
    reply_to = str(args.get("reply_to") or "").strip() or None

    try:
        context = build_context_for(work_dir)
        payload = submit_ask(
            context,
            ParsedAskCommand(
                project=None,
                target=agent_name,
                sender=caller,
                message=message,
                task_id=task_id,
                reply_to=reply_to,
            ),
        )
        if not payload.jobs:
            raise RuntimeError('ask submission returned no jobs')
        first_job = payload.jobs[0]
        response = {
            "project_id": payload.project_id,
            "submission_id": payload.submission_id,
            "job_id": first_job["job_id"],
            "agent_name": first_job.get("agent_name") or agent_name,
            "target_kind": first_job.get("target_kind"),
            "target_name": first_job.get("target_name") or agent_name,
            "status": first_job.get("status"),
        }
        if wait:
            terminal = watch_ask_job(
                context,
                first_job["job_id"],
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
                    "wait_hint": f"ccb ask wait {first_job['job_id']}",
                }
            )
        return tool_ok(response)
    except Exception as exc:
        return tool_error(str(exc))


def pend_task(args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("target") or "").strip().lower()
    if not target:
        return tool_error("target is required")

    work_dir = str(args.get("work_dir") or "").strip() or None
    try:
        context = build_context_for(work_dir)
        payload = pend_target(context, ParsedPendCommand(project=None, target=target))
        return tool_ok(
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
        return tool_error(str(exc))


def ping_agent(args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("target") or "ccbd").strip().lower() or "ccbd"
    work_dir = str(args.get("work_dir") or "").strip() or None
    try:
        context = build_context_for(work_dir)
        payload = ping_target(context, ParsedPingCommand(project=None, target=target))
        return tool_ok(payload)
    except Exception as exc:
        return tool_error(str(exc))


def handle_tool_call(name: str, args: dict[str, Any], *, caller: str) -> dict[str, Any]:
    if name == "ccb_ask_agent":
        return submit_task(args, caller=caller)
    if name == "ccb_pend_agent":
        return pend_task(args)
    if name == "ccb_ping_agent":
        return ping_agent(args)
    return tool_error(f"unknown tool: {name}")


__all__ = ['handle_tool_call']
