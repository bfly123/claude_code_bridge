from __future__ import annotations

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
    probe_client_factory=CcbdClient,
    runtime_client_factory=None,
    daemon_matches_project_config_fn=daemon_matches_project_config,
    shutdown_incompatible_daemon_fn=None,
) -> DaemonHandle | None:
    if not inspection.socket_connectable:
        return None
    runtime_client_factory = runtime_client_factory or probe_client_factory
    probe_client = probe_client_factory(context.paths.ccbd_socket_path)
    try:
        matches_config = daemon_matches_project_config_fn(context, probe_client)
    except CcbdClientError:
        # A transient ping failure is not evidence of config drift.
        return DaemonHandle(
            client=runtime_client_factory(context.paths.ccbd_socket_path),
            inspection=inspection,
            started=False,
        )
    if matches_config:
        return DaemonHandle(
            client=runtime_client_factory(context.paths.ccbd_socket_path),
            inspection=inspection,
            started=False,
        )
    if not restart_on_mismatch:
        return None
    if shutdown_incompatible_daemon_fn is None:
        raise ValueError('shutdown_incompatible_daemon_fn is required when restart_on_mismatch')
    shutdown_incompatible_daemon_fn(
        context,
        runtime_client_factory(context.paths.ccbd_socket_path),
    )
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
        client.stop_all(force=False)
    except CcbdClientError:
        pass
    deadline = time.time() + shutdown_timeout_s
    while time.time() < deadline:
        _, _, inspection = inspect_daemon_fn(context)
        if (
            not inspection.socket_connectable
            or inspection.health in unavailable_health_states
        ):
            return
        time.sleep(0.05)
    raise CcbdServiceError(
        f'{incompatible_daemon_error}; old ccbd did not shut down in time'
    )


__all__ = [
    'connect_compatible_daemon',
    'daemon_matches_project_config',
    'shutdown_incompatible_daemon',
]
