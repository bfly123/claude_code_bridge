from __future__ import annotations

from pathlib import Path
import shlex


def build_hook_command(
    *,
    provider: str,
    script_path: Path,
    python_executable: str,
    completion_dir: Path,
    agent_name: str,
    workspace_path: Path,
) -> str:
    parts = [
        python_executable,
        str(Path(script_path).expanduser()),
        '--provider',
        str(provider),
        '--completion-dir',
        str(Path(completion_dir).expanduser()),
        '--agent-name',
        str(agent_name),
        '--workspace',
        str(Path(workspace_path).expanduser()),
    ]
    return ' '.join(shlex.quote(str(part)) for part in parts)


__all__ = ['build_hook_command']
