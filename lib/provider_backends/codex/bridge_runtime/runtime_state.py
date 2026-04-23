from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from provider_backends.codex.runtime_artifacts import ensure_runtime_artifact_layout

from .binding import CodexBindingTracker
from .session import TerminalCodexSession


@dataclass(frozen=True)
class BridgePaths:
    runtime_dir: Path
    input_fifo: Path
    completion_dir: Path
    history_dir: Path
    history_file: Path
    bridge_log: Path


@dataclass(frozen=True)
class BridgeRuntimeState:
    paths: BridgePaths
    binding_tracker: CodexBindingTracker
    codex_session: TerminalCodexSession


def build_bridge_runtime_state(runtime_dir: Path, *, pane_id: str) -> BridgeRuntimeState:
    artifacts = ensure_runtime_artifact_layout(runtime_dir)
    paths = BridgePaths(
        runtime_dir=artifacts.runtime_dir,
        input_fifo=artifacts.input_fifo,
        completion_dir=artifacts.completion_dir,
        history_dir=artifacts.history_dir,
        history_file=artifacts.history_file,
        bridge_log=artifacts.bridge_log,
    )
    return BridgeRuntimeState(
        paths=paths,
        binding_tracker=CodexBindingTracker(runtime_dir),
        codex_session=TerminalCodexSession(pane_id),
    )


__all__ = [
    'BridgePaths',
    'BridgeRuntimeState',
    'build_bridge_runtime_state',
]
