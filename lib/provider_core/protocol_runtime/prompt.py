from __future__ import annotations

from .constants import DONE_PREFIX, REQ_ID_PREFIX


def wrap_codex_prompt(message: str, req_id: str) -> str:
    rendered = (message or '').rstrip()
    return (
        f'{REQ_ID_PREFIX} {req_id}\n\n'
        f'{rendered}\n\n'
        'IMPORTANT:\n'
        '- Reply normally.\n'
        '- Reply normally, in English.\n'
        '- End your reply with this exact final line (verbatim, on its own line):\n'
        f'{DONE_PREFIX} {req_id}\n'
    )


def wrap_codex_turn_prompt(message: str, req_id: str) -> str:
    rendered = (message or '').rstrip()
    return (
        f'{REQ_ID_PREFIX} {req_id}\n\n'
        f'{rendered}\n'
    )


__all__ = ['wrap_codex_prompt', 'wrap_codex_turn_prompt']
