from __future__ import annotations

import os
import time

from ccbd.socket_client import CcbdClientError

from .daemon import CcbdServiceError, connect_mounted_daemon
from .watch_runtime import (
    WatchEventBatch,
    default_watch_poll_interval_seconds,
    default_watch_timeout_seconds,
    watch_target as _watch_target_impl,
)


def _watch_timeout_seconds() -> float:
    return float(os.environ.get('CCB_WATCH_TIMEOUT_S', default_watch_timeout_seconds()))


def _watch_poll_interval_seconds() -> float:
    return float(os.environ.get('CCB_WATCH_POLL_INTERVAL_S', default_watch_poll_interval_seconds()))


def watch_target(context, command):
    return _watch_target_impl(
        context,
        command,
        connect_mounted_daemon_fn=connect_mounted_daemon,
        reconnect_error_classes=(CcbdClientError, CcbdServiceError),
        time_fn=time.time,
        sleep_fn=time.sleep,
        timeout_seconds_fn=_watch_timeout_seconds,
        poll_interval_seconds_fn=_watch_poll_interval_seconds,
    )


__all__ = ['WatchEventBatch', 'watch_target']
