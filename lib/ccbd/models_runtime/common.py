from __future__ import annotations

API_VERSION = 2
SCHEMA_VERSION = 2


class CcbdModelError(ValueError):
    pass


__all__ = ['API_VERSION', 'SCHEMA_VERSION', 'CcbdModelError']
