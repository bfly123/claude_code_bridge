from __future__ import annotations

from pathlib import Path
import json
import socket

from ccbd.api_models import RpcRequest, RpcResponse

from .errors import CcbdClientError


def connect_socket(socket_path: Path, *, timeout_s: float):
    if not hasattr(socket, 'AF_UNIX'):
        raise CcbdClientError('unix domain sockets are not supported on this platform')
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout_s)
    try:
        sock.connect(str(socket_path))
    except OSError as exc:
        sock.close()
        raise CcbdClientError(str(exc)) from exc
    return sock


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
