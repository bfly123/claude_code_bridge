from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


@dataclass(frozen=True)
class ClaudeStartPlan:
    cmd: list[str]
    run_cwd: str
    has_history: bool


@dataclass
class LauncherClaudeStartPlanner:
    auto: bool
    resume: bool
    project_root: Path
    invocation_dir: Path
    platform_name: str
    env: Mapping[str, str]
    which_fn: Callable[[str], str | None]
    get_latest_session_fn: Callable[[], tuple[str | None, bool, Path | None]]

    def find_claude_cmd(self) -> str:
        if self.platform_name == 'win32':
            for cmd in ('claude.exe', 'claude.cmd', 'claude.bat', 'claude'):
                path = self.which_fn(cmd)
                if path:
                    return path
            npm_paths = [
                Path(self.env.get('APPDATA', '')) / 'npm' / 'claude.cmd',
                Path(self.env.get('ProgramFiles', '')) / 'nodejs' / 'claude.cmd',
            ]
            for npm_path in npm_paths:
                if npm_path.exists():
                    return str(npm_path)
        else:
            path = self.which_fn('claude')
            if path:
                return path
        raise FileNotFoundError(
            '❌ Claude CLI not found. Install: npm install -g @anthropic-ai/claude-code'
        )

    def build_plan(self) -> ClaudeStartPlan:
        cmd = [self.find_claude_cmd()]
        if self.auto:
            cmd.append('--dangerously-skip-permissions')

        has_history = False
        resume_dir = None
        if self.resume:
            _, has_history, resume_dir = self.get_latest_session_fn()
            if has_history:
                cmd.append('--continue')

        run_cwd = self.project_root if self.resume else self.invocation_dir
        if self.resume and has_history and resume_dir:
            run_cwd = resume_dir

        return ClaudeStartPlan(
            cmd=cmd,
            run_cwd=str(run_cwd),
            has_history=has_history,
        )
