from __future__ import annotations

import argparse
from pathlib import Path

from .service import DualBridge


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Claude-Codex bridge')
    parser.add_argument('--runtime-dir', required=True, help='Runtime directory')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir)
    bridge = DualBridge(runtime_dir)
    return bridge.run()


__all__ = ['main', 'parse_args']
