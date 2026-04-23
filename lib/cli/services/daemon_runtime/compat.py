from __future__ import annotations

import os
import time

from agents.config_identity import project_config_identity_payload
from agents.config_loader import load_project_config
from ccbd.socket_client import CcbdClient, CcbdClientError

from .models import CcbdServiceError, DaemonHandle


def daemon_matches_project_config(context, client) -> bool:
    expected = project_config_identity_payload(
        load_project_config(context.project.project_root).config
    )
    payload = client.ping('ccbd')
    actual_signature = str(payload.get('config_signature') or '').strip()
    if actual_signature:
        return actual_signature == expected['config_signature']
    known_agents = payload.get('known_agents')
    if not isinstance(known_agents, list):
        return False
    actual_agents = tuple(
        str(item).strip().lower() for item in known_agents if str(item).strip()
    )
    return actual_agents == tuple(expected['known_agents'])


def connect_compatible_daemon(
    context,
    inspection,
    *,
    restart_on_mismatch: bool,
    client_factory=CcbdClient,
    daemon_matches_project_config_fn=daemon_matches_project_config,
    shutdown_incompatible_daemon_fn=None,
) -> DaemonHandle | None:
    if not inspection.socket_connectable:
        return None
    try:
        client = client_factory(context.paths.ccbd_ipc_ref, ipc_kind=context.paths.ccbd_ipc_kind)
    except TypeError:
        client = client_factory(context.paths.ccbd_ipc_ref)
    try:
        matches_config = daemon_matches_project_config_fn(context, client)
    except CcbdClientError:
        # A transient ping failure is not evidence of config drift.
        return DaemonHandle(client=client, inspection=inspection, started=False)
    if matches_config:
        return DaemonHandle(client=client, inspection=inspection, started=False)
    if not restart_on_mismatch:
        return None
    if shutdown_incompatible_daemon_fn is None:
        raise ValueError('shutdown_incompatible_daemon_fn is required when restart_on_mismatch')
    shutdown_incompatible_daemon_fn(context, client)
    return None


def shutdown_incompatible_daemon(
    context,
    client,
    *,
    inspect_daemon_fn,
    incompatible_daemon_error: str,
    shutdown_timeout_s: float,
    unavailable_health_states,
) -> None:
    try:
        client.shutdown()
    except CcbdClientError:
        pass
    tolerate_interrupts = _should_tolerate_keyboard_interrupt(context)
    deadline = _deadline_after(shutdown_timeout_s, tolerate_interrupts=tolerate_interrupts)
    while not _deadline_expired(deadline, tolerate_interrupts=tolerate_interrupts):
        _, _, inspection = inspect_daemon_fn(context)
        if (
            not inspection.socket_connectable
            or inspection.health in unavailable_health_states
        ):
            return
        _sleep(0.05, tolerate_interrupts=tolerate_interrupts)
    raise CcbdServiceError(
        f'{incompatible_daemon_error}; old ccbd did not shut down in time'
    )


def _should_tolerate_keyboard_interrupt(context) -> bool:
    return getattr(context.paths, 'ccbd_ipc_kind', None) == 'named_pipe'


def _deadline_after(duration_s: float, *, tolerate_interrupts: bool) -> float:
    return _monotonic_now(tolerate_interrupts=tolerate_interrupts) + max(0.0, float(duration_s))


def _deadline_expired(deadline: float, *, tolerate_interrupts: bool) -> bool:
    return _monotonic_now(tolerate_interrupts=tolerate_interrupts) >= deadline


def _monotonic_now(*, tolerate_interrupts: bool) -> float:
    while True:
        try:
            return time.monotonic()
        except KeyboardInterrupt:
            if not tolerate_interrupts:
                raise


def _sleep(duration_s: float, *, tolerate_interrupts: bool) -> None:
    deadline = _deadline_after(duration_s, tolerate_interrupts=tolerate_interrupts)
    while True:
        remaining = deadline - _monotonic_now(tolerate_interrupts=tolerate_interrupts)
        if remaining <= 0:
            return
        try:
            time.sleep(remaining)
            return
        except KeyboardInterrupt:
            if not tolerate_interrupts:
                raise


__all__ = [
    'connect_compatible_daemon',
    'daemon_matches_project_config',
    'shutdown_incompatible_daemon',
]
