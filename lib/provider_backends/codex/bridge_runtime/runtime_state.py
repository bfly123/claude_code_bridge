from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .binding import CodexBindingTracker
from .session import TerminalCodexSession


@dataclass(frozen=True)
class BridgePaths:
    runtime_dir: Path
    input_fifo: Path
    history_dir: Path
    history_file: Path
    bridge_log: Path


@dataclass(frozen=True)
class BridgeRuntimeState:
    paths: BridgePaths
    binding_tracker: CodexBindingTracker
    codex_session: TerminalCodexSession


def build_bridge_runtime_state(runtime_dir: Path, *, pane_id: str) -> BridgeRuntimeState:
    paths = BridgePaths(
        runtime_dir=runtime_dir,
        input_fifo=runtime_dir / 'input.fifo',
        history_dir=runtime_dir / 'history',
        history_file=(runtime_dir / 'history' / 'session.jsonl'),
        bridge_log=runtime_dir / 'bridge.log',
    )
    paths.history_dir.mkdir(parents=True, exist_ok=True)
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
