from __future__ import annotations


def parse_args(parser, tokens: list[str], *, error_message: str, error_type):
    try:
        return parser.parse_args(tokens)
    except SystemExit as exc:
        raise error_type(error_message) from exc


def require_no_extra(tokens: list[str], *, command: str, error_type) -> None:
    if tokens:
        raise error_type(f'{command} does not accept extra arguments: {tokens}')


__all__ = ['parse_args', 'require_no_extra']
