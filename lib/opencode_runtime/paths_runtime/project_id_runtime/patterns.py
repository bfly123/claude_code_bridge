from __future__ import annotations

import re

from provider_core.protocol import REQ_ID_PREFIX

REQ_ID_RE = re.compile(rf"{re.escape(REQ_ID_PREFIX)}\s*([0-9a-fA-F]{{32}}|\d{{8}}-\d{{6}}-\d{{3}}-\d+-\d+)")

__all__ = ['REQ_ID_RE']
