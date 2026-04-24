from __future__ import annotations

from ccbd.startup_policy import (
    CONTROL_PLANE_RPC_TIMEOUT_S,
    KEEPER_READY_TIMEOUT_S,
    STARTUP_PROGRESS_STALL_TIMEOUT_S,
    STARTUP_TRANSACTION_TIMEOUT_S,
)

# Compatibility alias for legacy imports and tests that still patch START_TIMEOUT_S.
START_TIMEOUT_S = STARTUP_TRANSACTION_TIMEOUT_S


__all__ = [
    'CONTROL_PLANE_RPC_TIMEOUT_S',
    'KEEPER_READY_TIMEOUT_S',
    'STARTUP_PROGRESS_STALL_TIMEOUT_S',
    'STARTUP_TRANSACTION_TIMEOUT_S',
    'START_TIMEOUT_S',
]
