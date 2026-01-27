"""
Provider registry for the unified ask daemon.
"""
from __future__ import annotations

import threading
from typing import Dict, Optional, Type

from askd.adapters.base import BaseProviderAdapter


class ProviderRegistry:
    """
    Registry for provider adapters.

    Manages registration and lookup of provider adapters by key.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._adapters: Dict[str, BaseProviderAdapter] = {}

    def register(self, adapter: BaseProviderAdapter) -> None:
        """Register a provider adapter."""
        with self._lock:
            self._adapters[adapter.key] = adapter

    def get(self, key: str) -> Optional[BaseProviderAdapter]:
        """Get a provider adapter by key."""
        with self._lock:
            return self._adapters.get(key)

    def keys(self) -> list[str]:
        """Get all registered provider keys."""
        with self._lock:
            return list(self._adapters.keys())

    def all(self) -> list[BaseProviderAdapter]:
        """Get all registered adapters."""
        with self._lock:
            return list(self._adapters.values())

    def start_all(self) -> None:
        """Call on_start for all adapters."""
        for adapter in self.all():
            try:
                adapter.on_start()
            except Exception:
                pass

    def stop_all(self) -> None:
        """Call on_stop for all adapters."""
        for adapter in self.all():
            try:
                adapter.on_stop()
            except Exception:
                pass
