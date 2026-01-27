"""
Unified Ask Daemon (askd) - Single daemon for all AI providers.

This module provides a unified daemon architecture that consolidates
caskd, gaskd, oaskd, daskd, and laskd into a single process.
"""
from __future__ import annotations

__all__ = [
    "UnifiedAskDaemon",
    "ProviderRegistry",
    "BaseProviderAdapter",
]
