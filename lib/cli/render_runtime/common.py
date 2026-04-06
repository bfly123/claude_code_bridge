from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import re


_PROTOCOL_LINE_RE = re.compile(r'^\s*CCB_(?:REQ_ID|BEGIN|DONE):.*$', re.MULTILINE)


def display_text(value: object) -> str:
    text = str(value or '')
    if not text:
        return ''
    text = _PROTOCOL_LINE_RE.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def render_mapping(payload: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(f'{key}: {value}' for key, value in payload.items())


def render_tmux_cleanup_summaries(items: Sequence[object]) -> tuple[str, ...]:
    lines: list[str] = []
    for item in items:
        socket_name = cleanup_field(getattr(item, 'socket_name', None), default='<default>')
        owned = cleanup_csv(getattr(item, 'owned_panes', ()) or ())
        active = cleanup_csv(getattr(item, 'active_panes', ()) or ())
        orphaned = cleanup_csv(getattr(item, 'orphaned_panes', ()) or ())
        killed = cleanup_csv(getattr(item, 'killed_panes', ()) or ())
        lines.append(
            'tmux_cleanup: '
            f'socket={socket_name} owned={owned} active={active} orphaned={orphaned} killed={killed}'
        )
    return tuple(lines)


def cleanup_csv(items: Iterable[object]) -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    return ','.join(values) if values else '-'


def cleanup_field(value: object, *, default: str) -> str:
    text = str(value or '').strip()
    return text or default


def write_lines(out, lines: Iterable[str]) -> None:
    for line in lines:
        print(line, file=out)


__all__ = ['display_text', 'render_mapping', 'render_tmux_cleanup_summaries', 'write_lines']
