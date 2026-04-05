from __future__ import annotations

from pathlib import Path
import json
import os
import socket

from ccbd.api_models import MessageEnvelope, RpcRequest, RpcResponse


class CcbdClientError(RuntimeError):
    pass


class CcbdClient:
    def __init__(self, socket_path: str | Path, *, timeout_s: float | None = None) -> None:
        self._socket_path = Path(socket_path)
        self._timeout_s = _resolve_timeout(timeout_s)

    def request(self, op: str, payload: dict | None = None) -> dict:
        req = RpcRequest(op=op, request=payload or {})
        if not hasattr(socket, 'AF_UNIX'):
            raise CcbdClientError('unix domain sockets are not supported on this platform')
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self._timeout_s)
        try:
            sock.connect(str(self._socket_path))
            sock.sendall((json.dumps(req.to_record(), ensure_ascii=False) + '\n').encode('utf-8'))
            raw = b''
            while b'\n' not in raw:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                raw += chunk
        except OSError as exc:
            raise CcbdClientError(str(exc)) from exc
        finally:
            sock.close()
        if not raw:
            raise CcbdClientError('empty response from ccbd')
        response = RpcResponse.from_record(json.loads(raw.split(b'\n', 1)[0].decode('utf-8')))
        if not response.ok:
            raise CcbdClientError(response.error or 'ccbd request failed')
        return response.payload

    def submit(self, request: MessageEnvelope) -> dict:
        return self.request('submit', request.to_record())

    def get(self, job_id: str) -> dict:
        return self.request('get', {'job_id': job_id})

    def watch(self, target: str, *, cursor: int = 0) -> dict:
        return self.request('watch', {'target': target, 'cursor': cursor})

    def queue(self, target: str = 'all') -> dict:
        return self.request('queue', {'target': target})

    def trace(self, target: str) -> dict:
        return self.request('trace', {'target': target})

    def resubmit(self, message_id: str) -> dict:
        return self.request('resubmit', {'message_id': message_id})

    def retry(self, target: str) -> dict:
        return self.request('retry', {'target': target})

    def inbox(self, agent_name: str) -> dict:
        return self.request('inbox', {'agent_name': agent_name})

    def ack(self, agent_name: str, inbound_event_id: str | None = None) -> dict:
        payload = {'agent_name': agent_name}
        if inbound_event_id:
            payload['inbound_event_id'] = inbound_event_id
        return self.request('ack', payload)

    def cancel(self, job_id: str) -> dict:
        return self.request('cancel', {'job_id': job_id})

    def start(
        self,
        *,
        agent_names: tuple[str, ...] = (),
        restore: bool = False,
        auto_permission: bool = False,
    ) -> dict:
        return self.request(
            'start',
            {
                'agent_names': list(agent_names),
                'restore': bool(restore),
                'auto_permission': bool(auto_permission),
            },
        )

    def attach(
        self,
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
        terminal_backend: str | None = None,
        pane_id: str | None = None,
        active_pane_id: str | None = None,
        pane_title_marker: str | None = None,
        pane_state: str | None = None,
        tmux_socket_name: str | None = None,
        session_file: str | None = None,
        session_id: str | None = None,
        lifecycle_state: str | None = None,
        managed_by: str | None = None,
        binding_source: str | None = 'external-attach',
    ) -> dict:
        return self.request(
            'attach',
            {
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
                'terminal_backend': terminal_backend,
                'pane_id': pane_id,
                'active_pane_id': active_pane_id,
                'pane_title_marker': pane_title_marker,
                'pane_state': pane_state,
                'tmux_socket_name': tmux_socket_name,
                'session_file': session_file,
                'session_id': session_id,
                'lifecycle_state': lifecycle_state,
                'managed_by': managed_by,
                'binding_source': binding_source,
            },
        )

    def restore(self, agent_name: str) -> dict:
        return self.request('restore', {'agent_name': agent_name})

    def ping(self, target: str = 'ccbd') -> dict:
        return self.request('ping', {'target': target})

    def shutdown(self) -> dict:
        return self.request('shutdown', {})

    def stop_all(self, *, force: bool = False) -> dict:
        return self.request('stop-all', {'force': bool(force)})


def _resolve_timeout(explicit: float | None) -> float:
    if explicit is not None:
        try:
            return max(0.1, float(explicit))
        except Exception:
            return 3.0
    for env_name in ('CCB_CCBD_CLIENT_TIMEOUT_S',):
        raw = os.environ.get(env_name)
        if not raw:
            continue
        try:
            return max(0.1, float(raw))
        except Exception:
            continue
    return 3.0


__all__ = ['CcbdClient', 'CcbdClientError']
