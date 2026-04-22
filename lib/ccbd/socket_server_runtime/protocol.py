from __future__ import annotations

import json

from ccbd.api_models import RpcRequest, RpcResponse


def handle_connection(server, conn) -> str | None:
    raw = b''
    while b'\n' not in raw:
        chunk = conn.recv(65536)
        if not chunk:
            break
        raw += chunk
    if not raw:
        return None
    request = None
    try:
        message = json.loads(raw.split(b'\n', 1)[0].decode('utf-8'))
        request = RpcRequest.from_record(message)
        handler = server._handlers.get(request.op)
        if handler is None:
            response = RpcResponse.failure(f'unknown op: {request.op}')
        else:
            guard = getattr(server, '_request_guard', None)
            rejection = guard(request.op) if guard is not None else None
            if rejection:
                response = RpcResponse.failure(rejection)
            else:
                response = RpcResponse.success(handler(request.request))
    except Exception as exc:
        response = RpcResponse.failure(str(exc))
    try:
        conn.sendall((json.dumps(response.to_record(), ensure_ascii=False) + '\n').encode('utf-8'))
    except OSError:
        return getattr(request, 'op', None)
    return getattr(request, 'op', None)


__all__ = ['handle_connection']
