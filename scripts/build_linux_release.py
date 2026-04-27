#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_release import *  # noqa: F401,F403
from build_release import main_for_target


def main() -> int:
    return main_for_target("linux")


if __name__ == "__main__":
    raise SystemExit(main())
