from __future__ import annotations

import time

from ccbd.socket_client import CcbdClientError

from .daemon import CcbdServiceError, connect_mounted_daemon
from .wait_runtime import WaitSummary, wait_for_replies as _wait_for_replies_impl


def wait_for_replies(context, command) -> WaitSummary:
    return _wait_for_replies_impl(
        context,
        command,
        connect_mounted_daemon_fn=connect_mounted_daemon,
        client_error_cls=CcbdClientError,
        service_error_cls=CcbdServiceError,
        monotonic_fn=time.monotonic,
        sleep_fn=time.sleep,
    )


__all__ = ['WaitSummary', 'wait_for_replies']
