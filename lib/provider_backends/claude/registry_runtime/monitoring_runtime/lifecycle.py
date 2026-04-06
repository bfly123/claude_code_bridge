from __future__ import annotations

import threading


def start_monitor(registry) -> None:
    if registry._monitor_thread is not None:
        return
    registry._start_root_watcher()
    registry._monitor_thread = threading.Thread(target=registry._monitor_loop, daemon=True)
    registry._monitor_thread.start()


def stop_monitor(registry) -> None:
    registry._stop.set()
    registry._stop_root_watcher()
    registry._stop_all_watchers()


def monitor_loop(registry) -> None:
    while not registry._stop.wait(registry.CHECK_INTERVAL):
        registry._check_all_sessions()


__all__ = ['monitor_loop', 'start_monitor', 'stop_monitor']
