from __future__ import annotations

from typing import Callable

from ccbd.api_models import MessageEnvelope


def bind_endpoint(client, *, name: str, endpoint) -> Callable[..., dict]:
    op, payload_builder = endpoint

    def call(*args, **kwargs):
        return client.request(op, payload_builder(*args, **kwargs))

    call.__name__ = name
    return call


def _payload_submit(request: MessageEnvelope) -> dict:
    return request.to_record()


def _payload_get(job_id: str) -> dict:
    return {'job_id': job_id}


def _payload_watch(target: str, *, cursor: int = 0) -> dict:
    return {'target': target, 'cursor': cursor}


def _payload_queue(target: str = 'all') -> dict:
    return {'target': target}


def _payload_trace(target: str) -> dict:
    return {'target': target}


def _payload_resubmit(message_id: str) -> dict:
    return {'message_id': message_id}


def _payload_retry(target: str) -> dict:
    return {'target': target}


def _payload_inbox(agent_name: str) -> dict:
    return {'agent_name': agent_name}


def _payload_ack(agent_name: str, inbound_event_id: str | None = None) -> dict:
    payload = {'agent_name': agent_name}
    if inbound_event_id:
        payload['inbound_event_id'] = inbound_event_id
    return payload


def _payload_cancel(job_id: str) -> dict:
    return {'job_id': job_id}


def _payload_start(
    *,
    agent_names: tuple[str, ...] = (),
    restore: bool = False,
    auto_permission: bool = False,
) -> dict:
    return {
        'agent_names': list(agent_names),
        'restore': bool(restore),
        'auto_permission': bool(auto_permission),
    }


def _payload_attach(
    *,
    agent_name: str,
    workspace_path: str,
    backend_type: str,
    pid: int | None = None,
    runtime_ref: str | None = None,
    session_ref: str | None = None,
    health: str | None = None,
    provider: str | None = None,
    runtime_root: str | None = None,
    runtime_pid: int | None = None,
    job_id: str | None = None,
    job_owner_pid: int | None = None,
    terminal_backend: str | None = None,
    pane_id: str | None = None,
    active_pane_id: str | None = None,
    pane_title_marker: str | None = None,
    pane_state: str | None = None,
    tmux_socket_name: str | None = None,
    tmux_socket_path: str | None = None,
    session_file: str | None = None,
    session_id: str | None = None,
    slot_key: str | None = None,
    window_id: str | None = None,
    workspace_epoch: int | None = None,
    lifecycle_state: str | None = None,
    managed_by: str | None = None,
    binding_source: str | None = 'external-attach',
) -> dict:
    return {
        'agent_name': agent_name,
        'workspace_path': workspace_path,
        'backend_type': backend_type,
        'pid': pid,
        'runtime_ref': runtime_ref,
        'session_ref': session_ref,
        'health': health,
        'provider': provider,
        'runtime_root': runtime_root,
        'runtime_pid': runtime_pid,
        'job_id': job_id,
        'job_owner_pid': job_owner_pid,
        'terminal_backend': terminal_backend,
        'pane_id': pane_id,
        'active_pane_id': active_pane_id,
        'pane_title_marker': pane_title_marker,
        'pane_state': pane_state,
        'tmux_socket_name': tmux_socket_name,
        'tmux_socket_path': tmux_socket_path,
        'session_file': session_file,
        'session_id': session_id,
        'slot_key': slot_key,
        'window_id': window_id,
        'workspace_epoch': workspace_epoch,
        'lifecycle_state': lifecycle_state,
        'managed_by': managed_by,
        'binding_source': binding_source,
    }


def _payload_restore(agent_name: str) -> dict:
    return {'agent_name': agent_name}


def _payload_ping(target: str = 'ccbd') -> dict:
    return {'target': target}


def _payload_shutdown() -> dict:
    return {}


def _payload_stop_all(*, force: bool = False) -> dict:
    return {'force': bool(force)}


client_endpoints = {
    'submit': ('submit', _payload_submit),
    'get': ('get', _payload_get),
    'watch': ('watch', _payload_watch),
    'queue': ('queue', _payload_queue),
    'trace': ('trace', _payload_trace),
    'resubmit': ('resubmit', _payload_resubmit),
    'retry': ('retry', _payload_retry),
    'inbox': ('inbox', _payload_inbox),
    'ack': ('ack', _payload_ack),
    'cancel': ('cancel', _payload_cancel),
    'start': ('start', _payload_start),
    'attach': ('attach', _payload_attach),
    'restore': ('restore', _payload_restore),
    'ping': ('ping', _payload_ping),
    'shutdown': ('shutdown', _payload_shutdown),
    'stop_all': ('stop-all', _payload_stop_all),
}


__all__ = ['bind_endpoint', 'client_endpoints']
