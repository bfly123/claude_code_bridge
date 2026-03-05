from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class AsyncDispatchConfig:
    require_provider_ack: bool
    provider_ack_timeout_s: float
    dispatch_ack_timeout_s: float
    provider_ack_checker: Callable[[str, float], tuple[bool, str, str]]
    poll_interval_s: float = 0.1


@dataclass
class AsyncTaskContext:
    provider: str
    message: str
    timeout: float
    caller: str
    task_id: str
    log_dir: Path
    log_file: Path
    ask_cmd: str
    work_dir: str
    run_dir: str

    @property
    def ack_marker(self) -> str:
        return f"[CCB_TASK_ACK task={self.task_id}]"


def wait_for_log_marker(
    log_file: Path,
    marker: str,
    timeout_s: float,
    poll_interval_s: float = 0.1,
) -> tuple[bool, str]:
    deadline = time.time() + timeout_s
    offset = 0
    while time.time() < deadline:
        try:
            if log_file.exists():
                size = log_file.stat().st_size
                if size < offset:
                    offset = 0
                if size > offset:
                    with log_file.open("r", encoding="utf-8", errors="replace") as fh:
                        fh.seek(offset)
                        chunk = fh.read()
                        offset = fh.tell()
                    if marker in chunk:
                        return True, marker
        except Exception:
            pass
        time.sleep(max(0.01, poll_interval_s))
    return False, f"marker timeout after {timeout_s:.1f}s: {marker}"


class AsyncDispatcher:
    def __init__(self, ctx: AsyncTaskContext, cfg: AsyncDispatchConfig):
        self.ctx = ctx
        self.cfg = cfg

    def submit(self) -> tuple[bool, str, str]:
        ok, reason, details = self._preflight_provider_ack()
        if not ok:
            return False, reason, details
        self._spawn_background()
        got_ack, ack_details = wait_for_log_marker(
            self.ctx.log_file,
            self.ctx.ack_marker,
            self.cfg.dispatch_ack_timeout_s,
            self.cfg.poll_interval_s,
        )
        if not got_ack:
            return False, "dispatch_ack_timeout", ack_details
        return True, "ok", self.ctx.task_id

    def _preflight_provider_ack(self) -> tuple[bool, str, str]:
        if not self.cfg.require_provider_ack:
            return True, "ok", "provider ack bypassed"
        return self.cfg.provider_ack_checker(self.ctx.provider, self.cfg.provider_ack_timeout_s)

    def _spawn_background(self) -> None:
        if os.name == "nt":
            self._spawn_windows()
        else:
            self._spawn_unix()

    def _spawn_windows(self) -> None:
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        CREATE_NEW_PROCESS_GROUP = 0x00000200

        msg_file = self.ctx.log_dir / f"ask-{self.ctx.provider}-{self.ctx.task_id}.msg"
        msg_file.write_text(self.ctx.message, encoding="utf-8")

        script_file = self.ctx.log_dir / f"ask-{self.ctx.provider}-{self.ctx.task_id}.ps1"
        script_content = f'''$ErrorActionPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output "{self.ctx.ack_marker}"
$env:CCB_REQ_ID = "{self.ctx.task_id}"
$env:CCB_CALLER = "{self.ctx.caller}"
$env:CCB_WORK_DIR = "{self.ctx.work_dir}"
Get-Content -Path "{msg_file}" -Encoding UTF8 | python "{self.ctx.ask_cmd}" {self.ctx.provider} --foreground --timeout {self.ctx.timeout}
'''
        script_file.write_text(script_content, encoding="utf-8")

        subprocess.Popen(
            ["powershell", "-ExecutionPolicy", "Bypass", "-NoProfile", "-File", str(script_file)],
            stdin=subprocess.DEVNULL,
            stdout=open(self.ctx.log_file, "w"),
            stderr=subprocess.STDOUT,
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        )

    def _spawn_unix(self) -> None:
        email_env_lines = ""
        if self.ctx.caller == "email":
            for key in ("CCB_EMAIL_REQ_ID", "CCB_EMAIL_MSG_ID", "CCB_EMAIL_FROM"):
                val = os.environ.get(key, "")
                if val:
                    email_env_lines += f'export {key}="{val}"\n'

        run_dir_line = f'export CCB_RUN_DIR="{self.ctx.run_dir}"\n' if self.ctx.run_dir else ""

        bg_script = f'''
echo "{self.ctx.ack_marker}"
export CCB_REQ_ID="{self.ctx.task_id}"
export CCB_CALLER="{self.ctx.caller}"
export CCB_WORK_DIR="{self.ctx.work_dir}"
{run_dir_line}{email_env_lines}python3 "{self.ctx.ask_cmd}" {self.ctx.provider} --foreground --timeout {self.ctx.timeout} <<'ASKEOF'
{self.ctx.message}
ASKEOF
'''
        script_file = self.ctx.log_dir / f"ask-{self.ctx.provider}-{self.ctx.task_id}.sh"
        script_file.write_text(bg_script, encoding="utf-8")
        script_file.chmod(0o755)

        subprocess.Popen(
            f'nohup sh "{script_file}" > "{self.ctx.log_file}" 2>&1 &',
            shell=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
