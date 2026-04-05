from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Callable, Optional

from agents.config_loader import ensure_bootstrap_project_config
from cli.context import CliContext, CliContextBuilder
from cli.models import ParsedAskCommand, ParsedStartCommand
from cli.services.ask import exit_code_for_ask_status, submit_ask, watch_ask_job
from provider_sessions.files import resolve_project_config_dir

from memory.types import TransferContext


def build_context(project: str | None, *, cwd: Path | None = None) -> CliContext:
    command = ParsedStartCommand(project=project, agent_names=(), restore=False, auto_permission=False)
    context = CliContextBuilder().build(command, cwd=(cwd or Path.cwd()), bootstrap_if_missing=True)
    ensure_bootstrap_project_config(context.project.project_root)
    return context


def submit_agent_target(
    context: CliContext,
    *,
    target: str,
    message: str,
    sender: str,
    task_id: str | None,
    reply_to: str | None = None,
    mode: str = "ask",
    silence_on_success: bool = False,
) -> dict:
    summary = submit_ask(
        context,
        ParsedAskCommand(
            project=None,
            target=target,
            sender=sender,
            message=message,
            task_id=task_id,
            reply_to=reply_to,
            mode=mode,
            silence=silence_on_success,
        ),
    )
    if len(summary.jobs) != 1:
        raise RuntimeError("programmatic agent submission requires exactly one accepted job")
    return dict(summary.jobs[0])


def watch_job(
    context: CliContext,
    job_id: str,
    out: StringIO,
    *,
    timeout: float,
    emit_output: bool,
):
    return watch_ask_job(context, job_id, out, timeout=timeout, emit_output=emit_output)


def exit_code_for_status(status: str | None, *, reply: str) -> int:
    return exit_code_for_ask_status(status, reply=reply)


def send_to_agent(
    *,
    agent_name: str,
    formatted: str,
    work_dir: Path | None = None,
) -> tuple[bool, str]:
    try:
        context = build_context(None, cwd=work_dir)
        payload = submit_agent_target(
            context,
            target=agent_name,
            message=formatted,
            sender='user',
            task_id=None,
        )
        terminal = watch_job(
            context,
            payload["job_id"],
            StringIO(),
            timeout=60,
            emit_output=False,
        )
        reply = terminal.reply or ""
        if exit_code_for_status(terminal.status, reply=reply) == 0:
            return True, reply
        return False, reply or f"Command failed with status {terminal.status}"
    except Exception as exc:
        return False, str(exc)


def save_transfer(
    *,
    work_dir: Path,
    format_output_fn: Callable[[TransferContext, str], str],
    context: TransferContext,
    fmt: str = "markdown",
    target_agent: Optional[str] = None,
    filename: Optional[str] = None,
) -> Path:
    target_history_dir = history_dir(work_dir)
    target_history_dir.mkdir(parents=True, exist_ok=True)

    ext = {"markdown": "md", "plain": "txt", "json": "json"}.get(fmt, "md")
    if filename:
        safe = str(filename).strip().replace("/", "-").replace("\\", "-")
        if not Path(safe).suffix:
            safe = f"{safe}.{ext}"
        filepath = target_history_dir / safe
    else:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        session_short = context.source_session_id[:8]
        source_provider = (context.source_provider or context.metadata.get("provider") or "session").strip().lower()
        if not source_provider:
            source_provider = "session"
        source_provider = source_provider.replace("/", "-").replace("\\", "-")
        provider_suffix = f"-to-{target_agent}" if target_agent else ""
        filepath = target_history_dir / f"{source_provider}-{ts}-{session_short}{provider_suffix}.{ext}"

    formatted = format_output_fn(context, fmt)
    filepath.write_text(formatted, encoding="utf-8")
    return filepath


def history_dir(work_dir: Path) -> Path:
    try:
        resolved_work_dir = Path(work_dir).expanduser()
    except Exception:
        resolved_work_dir = Path.cwd()

    base = resolve_project_config_dir(resolved_work_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / "history"
