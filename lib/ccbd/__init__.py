from __future__ import annotations

__all__ = ['CcbdApp', 'CcbdClient', 'CcbdClientError']


def __getattr__(name: str):
    if name == 'CcbdApp':
        from .app import CcbdApp

        return CcbdApp
    if name == 'CcbdClient':
        from .socket_client import CcbdClient

        return CcbdClient
    if name == 'CcbdClientError':
        from .socket_client import CcbdClientError

        return CcbdClientError
    raise AttributeError(name)
