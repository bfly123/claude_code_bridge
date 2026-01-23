"""Cursor Agent utilities for parsing output and extracting metadata."""

from __future__ import annotations

import json
import re
from typing import Optional, Tuple


def parse_json_output(output: str) -> Tuple[Optional[str], Optional[str], Optional[bool]]:
    """Parse JSON output from cursor-agent.

    Args:
        output: Raw output from cursor-agent with --output-format json

    Returns:
        Tuple of (session_id, result_text, is_error).
        Returns (None, None, None) if parsing fails.
    """
    try:
        data = json.loads(output.strip())
        session_id = data.get("session_id")
        result_text = data.get("result", "")
        is_error = data.get("is_error", False)
        return session_id, result_text, is_error
    except (json.JSONDecodeError, AttributeError):
        return None, None, None


def extract_chat_id_fallback(output: str) -> Optional[str]:
    """Fallback: Extract chat_id from cursor-agent text output if JSON parsing fails.

    Args:
        output: Raw text output from cursor-agent

    Returns:
        Extracted chat ID (UUID format) or None if not found.
    """
    patterns = [
        r'"session_id":\s*"([a-f0-9-]{36})"',
        r'"chatId":\s*"([a-f0-9-]{36})"',
        r'chatId:\s*([a-f0-9-]{36})',
        r'chat[_-]?id[=:]\s*([a-f0-9-]{36})',
    ]
    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            return match.group(1)
    return None
