from __future__ import annotations

import importlib
import time
from dataclasses import dataclass
from typing import Callable


_WARMUP_SPECS: dict[str, tuple[str, str]] = {
    "codex": ("provider_backends.codex.comm", "CodexCommunicator"),
    "droid": ("provider_backends.droid.comm", "DroidCommunicator"),
    "opencode": ("provider_backends.opencode.comm", "OpenCodeCommunicator"),
}


def probe_provider_health(provider: str) -> tuple[bool, str] | None:
    spec = _WARMUP_SPECS.get(str(provider or "").strip().lower())
    if spec is None:
        return None
    module = importlib.import_module(spec[0])
    communicator_cls = getattr(module, spec[1])
    communicator = communicator_cls(lazy_init=True)
    healthy, message = communicator.ping(display=False)
    return bool(healthy), str(message or "").strip()


@dataclass
class LauncherWarmupService:
    probe_fn: Callable[[str], tuple[bool, str] | None] = probe_provider_health
    sleep_fn: Callable[[float], None] = time.sleep
    time_fn: Callable[[], float] = time.time
    print_fn: Callable[[str], None] = print

    def warmup_provider(self, provider: str, timeout: float = 8.0) -> bool:
        provider = (provider or "").strip().lower()
        if provider == "gemini":
            return True
        if provider not in _WARMUP_SPECS:
            return False

        self.print_fn(f"🔧 Warmup: {provider}")
        deadline = self.time_fn() + timeout
        last_output = ""
        sleep_s = 0.3
        while self.time_fn() < deadline:
            try:
                result = self.probe_fn(provider)
            except Exception as exc:
                result = (False, str(exc).strip())
            if result is None:
                return False
            healthy, message = result
            last_output = str(message or "").strip()
            if healthy:
                if last_output:
                    self.print_fn(last_output)
                return True
            self.sleep_fn(sleep_s)
            sleep_s = min(1.0, sleep_s * 1.5)

        if last_output:
            self.print_fn(last_output)
        self.print_fn(f"⚠️ Warmup failed: {provider}")
        return False
