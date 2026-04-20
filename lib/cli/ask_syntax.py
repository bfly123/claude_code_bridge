from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedAskRoute:
    target: str
    sender: str | None
    message: str


def parse_ask_route(tokens: list[str], *, command_name: str) -> ParsedAskRoute:
    remaining = list(tokens)
    if len(remaining) < 2:
        raise ValueError(f'{command_name} requires <target> [from <sender>] <message>')

    target = remaining.pop(0).strip()
    if not target:
        raise ValueError(f'{command_name} target cannot be empty')

    sender: str | None = None
    if remaining and remaining[0] == 'from':
        if len(remaining) < 3:
            raise ValueError(f'{command_name} requires <target> [from <sender>] <message>')
        remaining.pop(0)
        sender = remaining.pop(0).strip()
        if not sender:
            raise ValueError(f'{command_name} sender cannot be empty')

    if remaining and remaining[0] == '--':
        remaining.pop(0)
    message = ' '.join(remaining).strip()
    if not message:
        raise ValueError(f'{command_name} message cannot be empty')

    return ParsedAskRoute(target=target, sender=sender, message=message)


__all__ = ['ParsedAskRoute', 'parse_ask_route']
