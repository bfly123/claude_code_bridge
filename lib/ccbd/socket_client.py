from __future__ import annotations

from pathlib import Path
import os

from ccbd.api_models import RpcRequest
from .socket_client_runtime import (
    CcbdClientError,
    bind_endpoint,
    client_endpoints,
    connect_socket,
    decode_response,
    recv_response_line,
    send_request,
)


class CcbdClient:
    def __init__(self, socket_path: str | Path, *, timeout_s: float | None = None) -> None:
        self._socket_path = Path(socket_path)
        self._timeout_s = _resolve_timeout(timeout_s)

    def request(self, op: str, payload: dict | None = None) -> dict:
        req = RpcRequest(op=op, request=payload or {})
        try:
            sock = connect_socket(self._socket_path, timeout_s=self._timeout_s)
        except OSError as exc:
            raise CcbdClientError(str(exc)) from exc
        try:
            send_request(sock, req)
            raw = recv_response_line(sock)
        except OSError as exc:
            raise CcbdClientError(str(exc)) from exc
        finally:
            sock.close()
        if not raw:
            raise CcbdClientError('empty response from ccbd')
        response = decode_response(raw)
        if not response.ok:
            raise CcbdClientError(response.error or 'ccbd request failed')
        return response.payload

    def __getattr__(self, name: str):
        endpoint = client_endpoints.get(name)
        if endpoint is None:
            raise AttributeError(name)
        call = bind_endpoint(self, name=name, endpoint=endpoint)
        object.__setattr__(self, name, call)
        return call


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
