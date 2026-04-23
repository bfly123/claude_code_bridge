from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodexRuntimeArtifacts:
    runtime_dir: Path
    input_fifo: Path
    output_fifo: Path
    completion_dir: Path
    history_dir: Path
    history_file: Path
    bridge_log: Path
    bridge_stdout_log: Path
    bridge_stderr_log: Path
    bridge_pid: Path
    codex_pid: Path


def codex_runtime_artifact_layout(runtime_dir: Path) -> CodexRuntimeArtifacts:
    runtime_dir = Path(runtime_dir)
    return CodexRuntimeArtifacts(
        runtime_dir=runtime_dir,
        input_fifo=runtime_dir / 'input.fifo',
        output_fifo=runtime_dir / 'output.fifo',
        completion_dir=runtime_dir / 'completion',
        history_dir=runtime_dir / 'history',
        history_file=runtime_dir / 'history' / 'session.jsonl',
        bridge_log=runtime_dir / 'bridge.log',
        bridge_stdout_log=runtime_dir / 'bridge.stdout.log',
        bridge_stderr_log=runtime_dir / 'bridge.stderr.log',
        bridge_pid=runtime_dir / 'bridge.pid',
        codex_pid=runtime_dir / 'codex.pid',
    )


def ensure_runtime_artifact_layout(runtime_dir: Path) -> CodexRuntimeArtifacts:
    artifacts = codex_runtime_artifact_layout(runtime_dir)
    artifacts.runtime_dir.mkdir(parents=True, exist_ok=True)
    artifacts.completion_dir.mkdir(parents=True, exist_ok=True)
    artifacts.history_dir.mkdir(parents=True, exist_ok=True)
    _touch_file(artifacts.bridge_log)
    return artifacts


def _touch_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8'):
        pass


__all__ = [
    'CodexRuntimeArtifacts',
    'codex_runtime_artifact_layout',
    'ensure_runtime_artifact_layout',
]
