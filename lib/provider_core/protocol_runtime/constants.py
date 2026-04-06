from __future__ import annotations

import re


REQ_ID_PREFIX = 'CCB_REQ_ID:'
BEGIN_PREFIX = 'CCB_BEGIN:'
DONE_PREFIX = 'CCB_DONE:'

LEGACY_HEX_REQ_ID_PATTERN = r'[0-9a-fA-F]{32}'
LEGACY_TIMESTAMP_REQ_ID_PATTERN = r'\d{8}-\d{6}-\d{3}-\d+-\d+'
JOB_REQ_ID_PATTERN = r'job_[a-z0-9]+'
ANY_REQ_ID_PATTERN = rf'(?:{JOB_REQ_ID_PATTERN}|{LEGACY_HEX_REQ_ID_PATTERN}|{LEGACY_TIMESTAMP_REQ_ID_PATTERN})'
REQ_ID_BOUNDARY_PATTERN = r'(?=[^A-Za-z0-9_-]|$)'
DONE_LINE_RE_TEMPLATE = r'^\s*CCB_DONE:\s*{req_id}\s*$'
_TRAILING_DONE_TAG_RE = re.compile(
    rf'^\s*(?!CCB_DONE\s*:)[A-Z][A-Z0-9_]*_DONE(?:\s*:\s*{ANY_REQ_ID_PATTERN})?\s*$'
)
ANY_DONE_LINE_RE = re.compile(rf'^\s*CCB_DONE:\s*{ANY_REQ_ID_PATTERN}\s*$', re.IGNORECASE)


def done_line_re(req_id: str) -> re.Pattern[str]:
    return re.compile(DONE_LINE_RE_TEMPLATE.format(req_id=re.escape(req_id)))


def is_trailing_noise_line(line: str) -> bool:
    if (line or '').strip() == '':
        return True
    return bool(_TRAILING_DONE_TAG_RE.match(line or ''))


__all__ = [
    'ANY_DONE_LINE_RE',
    'ANY_REQ_ID_PATTERN',
    'BEGIN_PREFIX',
    'DONE_PREFIX',
    'REQ_ID_BOUNDARY_PATTERN',
    'REQ_ID_PREFIX',
    'done_line_re',
    'is_trailing_noise_line',
]
