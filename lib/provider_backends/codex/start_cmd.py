from __future__ import annotations

from pathlib import Path
import re
import shlex
from typing import Mapping

_CODEX_RESUME_CMD_RE = re.compile(r'\bcodex\b(?:[^;\n]*?)\bresume\s+(?P<session>[^\s;]+)')


def extract_resume_session_id(command: object) -> str | None:
    raw = str(command or '').strip()
    if not raw:
        return None
    match = _CODEX_RESUME_CMD_RE.search(raw)
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


def build_resume_start_cmd(command: object, session_id: object) -> str:
    normalized_session_id = str(session_id or '').strip()
    if not normalized_session_id:
        return str(command or '').strip()
    raw = str(command or '').strip()
    if not raw:
        return f'codex resume {shlex.quote(normalized_session_id)}'
    shell_prefix, codex_segment = _split_last_shell_segment(raw)
    rebuilt_segment = _rewrite_codex_segment(codex_segment, normalized_session_id)
    if not rebuilt_segment:
        rebuilt_segment = f'codex resume {shlex.quote(normalized_session_id)}'
    if shell_prefix:
        return f'{shell_prefix}; {rebuilt_segment}'
    return rebuilt_segment


def effective_start_cmd(data: Mapping[str, object]) -> str:
    if not isinstance(data, Mapping):
        return ''
    start_cmd = str(data.get('start_cmd') or '').strip()
    codex_start_cmd = str(data.get('codex_start_cmd') or '').strip()
    session_id = (
        str(data.get('codex_session_id') or '').strip()
        or extract_resume_session_id(codex_start_cmd)
        or extract_resume_session_id(start_cmd)
        or ''
    )
    if session_id and start_cmd:
        if not codex_start_cmd or _looks_like_bare_resume_cmd(codex_start_cmd):
            return build_resume_start_cmd(start_cmd, session_id)
    return codex_start_cmd or start_cmd


def persist_resume_start_cmd_fields(data: dict[str, object], session_id: object) -> str | None:
    if not isinstance(data, dict):
        return None
    normalized_session_id = str(session_id or '').strip()
    if not normalized_session_id:
        return None
    template = _resume_template_command(data)
    resume_start_cmd = build_resume_start_cmd(template, normalized_session_id)
    data['codex_start_cmd'] = resume_start_cmd
    data['start_cmd'] = resume_start_cmd
    return resume_start_cmd


def _resume_template_command(data: Mapping[str, object]) -> str:
    start_cmd = str(data.get('start_cmd') or '').strip()
    codex_start_cmd = str(data.get('codex_start_cmd') or '').strip()
    if start_cmd and not _looks_like_bare_resume_cmd(start_cmd):
        return start_cmd
    if codex_start_cmd:
        return codex_start_cmd
    return start_cmd


def _looks_like_bare_resume_cmd(command: str) -> bool:
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
    codex_index = _find_codex_token_index(tokens)
    if codex_index is None:
        return False
    return codex_index + 2 == len(tokens) - 1 and tokens[codex_index + 1] == 'resume'


def _split_last_shell_segment(command: str) -> tuple[str, str]:
    prefix, separator, tail = str(command or '').rpartition(';')
    if not separator:
        return '', str(command or '').strip()
    return prefix.strip(), tail.strip()


def _rewrite_codex_segment(segment: str, session_id: str) -> str | None:
    try:
        tokens = shlex.split(segment)
    except Exception:
        return None
    if not tokens:
        return None
    codex_index = _find_codex_token_index(tokens)
    if codex_index is None:
        return None
    resume_index = None
    for index in range(codex_index + 1, len(tokens)):
        if tokens[index] == 'resume':
            resume_index = index
            break
    base_tokens = tokens[:resume_index] if resume_index is not None else list(tokens)
    base_tokens.extend(['resume', session_id])
    return ' '.join(shlex.quote(str(token)) for token in base_tokens)


def _find_codex_token_index(tokens: list[str]) -> int | None:
    for index, token in enumerate(tokens):
        try:
            if Path(token).name == 'codex':
                return index
        except Exception:
            if token == 'codex':
                return index
    return None


__all__ = [
    'build_resume_start_cmd',
    'effective_start_cmd',
    'extract_resume_session_id',
    'persist_resume_start_cmd_fields',
]
