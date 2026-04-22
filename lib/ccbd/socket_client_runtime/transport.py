from __future__ import annotations

import json

from ccbd.api_models import RpcRequest, RpcResponse
from ccbd.ipc import connect_client

from .errors import CcbdClientError


def connect_socket(socket_path, *, timeout_s: float, ipc_kind: str | None = None):
    try:
        return connect_client(socket_path, timeout_s=timeout_s, ipc_kind=ipc_kind)
    except OSError as exc:
        raise CcbdClientError(str(exc)) from exc


def send_request(sock, request: RpcRequest) -> None:
    payload = json.dumps(request.to_record(), ensure_ascii=False) + '\n'
    sock.sendall(payload.encode('utf-8'))


def recv_response_line(sock) -> bytes:
    raw = b''
    while b'\n' not in raw:
        chunk = sock.recv(65536)
        if not chunk:
            break
        raw += chunk
    return raw


def decode_response(raw: bytes) -> RpcResponse:
    line = raw.split(b'\n', 1)[0].decode('utf-8')
    return RpcResponse.from_record(json.loads(line))


__all__ = ['connect_socket', 'decode_response', 'recv_response_line', 'send_request']
