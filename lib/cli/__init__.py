"""
CLI package surface for the current agent-first runtime.

The package exposes actively used modules and helpers via lazy attribute
resolution so callers can use a stable surface without creating import
cycles during package initialization.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "CliContext",
    "CliContextBuilder",
    "CliParser",
    "CliUsageError",
    "auxiliary",
    "kill",
    "management",
    "phase2",
    "router",
    "run_cli_entrypoint",
]


def __getattr__(name: str) -> Any:
    if name in {"auxiliary", "kill", "management", "phase2", "router"}:
        return import_module(f".{name}", __name__)
    if name in {"CliContext", "CliContextBuilder"}:
        module = import_module(".context", __name__)
        return getattr(module, name)
    if name in {"CliParser", "CliUsageError"}:
        module = import_module(".parser", __name__)
        return getattr(module, name)
    if name == "run_cli_entrypoint":
        module = import_module(".entrypoint", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
