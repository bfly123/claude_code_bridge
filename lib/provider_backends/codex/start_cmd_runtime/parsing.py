from __future__ import annotations

from pathlib import Path
import re
import shlex

CODEX_RESUME_CMD_RE = re.compile(r'\bcodex\b(?:[^;\n]*?)\bresume\s+(?P<session>[^\s;]+)')


def extract_resume_session_id(command: object) -> str | None:
    raw = str(command or '').strip()
    if not raw:
        return None
    match = CODEX_RESUME_CMD_RE.search(raw)
    if match is not None:
        session_id = str(match.group('session') or '').strip()
        return session_id or None
    try:
        tokens = shlex.split(raw)
    except Exception:
        return None
    for index, token in enumerate(tokens[:-1]):
        if token == 'resume':
            session_id = str(tokens[index + 1] or '').strip()
            if session_id:
                return session_id
    return None


def looks_like_bare_resume_cmd(command: str) -> bool:
    raw = str(command or '').strip()
    if not raw:
        return False
    if ';' in raw or 'CODEX_' in raw or ' export ' in f' {raw} ':
        return False
    try:
        tokens = shlex.split(raw)
    except Exception:
        return False
    if len(tokens) < 3:
        return False
    codex_index = find_codex_token_index(tokens)
    if codex_index is None:
        return False
    return codex_index + 2 == len(tokens) - 1 and tokens[codex_index + 1] == 'resume'


def find_codex_token_index(tokens: list[str]) -> int | None:
    for index, token in enumerate(tokens):
        try:
            if Path(token).name == 'codex':
                return index
        except Exception:
            if token == 'codex':
                return index
    return None


__all__ = ['extract_resume_session_id', 'find_codex_token_index', 'looks_like_bare_resume_cmd']
