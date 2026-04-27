from __future__ import annotations

import shlex

from .parsing import find_codex_token_index


def build_resume_start_cmd(command: object, session_id: object) -> str:
    normalized_session_id = str(session_id or '').strip()
    if not normalized_session_id:
        return str(command or '').strip()
    raw = str(command or '').strip()
    if not raw:
        return f'codex resume {shlex.quote(normalized_session_id)}'
    shell_prefix, codex_segment = split_last_shell_segment(raw)
    rebuilt_segment = rewrite_codex_segment(codex_segment, normalized_session_id)
    if not rebuilt_segment:
        rebuilt_segment = f'codex resume {shlex.quote(normalized_session_id)}'
    if shell_prefix:
        return f'{shell_prefix}; {rebuilt_segment}'
    return rebuilt_segment


def strip_resume_start_cmd(command: object) -> str:
    raw = str(command or '').strip()
    if not raw:
        return ''
    shell_prefix, codex_segment = split_last_shell_segment(raw)
    stripped_segment = strip_resume_from_codex_segment(codex_segment)
    if stripped_segment is None:
        stripped_segment = codex_segment
    if shell_prefix:
        return f'{shell_prefix}; {stripped_segment}'
    return stripped_segment


def split_last_shell_segment(command: str) -> tuple[str, str]:
    prefix, separator, tail = str(command or '').rpartition(';')
    if not separator:
        return '', str(command or '').strip()
    return prefix.strip(), tail.strip()


def strip_resume_from_codex_segment(segment: str) -> str | None:
    try:
        tokens = shlex.split(segment)
    except Exception:
        return None
    if not tokens:
        return None
    codex_index = find_codex_token_index(tokens)
    if codex_index is None:
        return None
    resume_index = None
    for index in range(codex_index + 1, len(tokens)):
        if tokens[index] == 'resume':
            resume_index = index
            break
    base_tokens = tokens[:resume_index] if resume_index is not None else list(tokens)
    if not base_tokens:
        return None
    return ' '.join(shlex.quote(str(token)) for token in base_tokens)


def rewrite_codex_segment(segment: str, session_id: str) -> str | None:
    try:
        tokens = shlex.split(segment)
    except Exception:
        return None
    if not tokens:
        return None
    codex_index = find_codex_token_index(tokens)
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


__all__ = [
    'build_resume_start_cmd',
    'rewrite_codex_segment',
    'split_last_shell_segment',
    'strip_resume_from_codex_segment',
    'strip_resume_start_cmd',
]
