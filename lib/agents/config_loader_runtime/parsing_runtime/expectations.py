from __future__ import annotations

from typing import Any

from ..common import ConfigValidationError


def expect_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigValidationError(f'{field_name} must be a table/object')
    return dict(value)


def expect_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ConfigValidationError(f'{field_name} must be a string')
    text = value.strip()
    if not text:
        raise ConfigValidationError(f'{field_name} cannot be empty')
    return text


def expect_bool(value: Any, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigValidationError(f'{field_name} must be a boolean')
    return value


def expect_string_list(value: Any, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ConfigValidationError(f'{field_name} must be a list of strings')
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ConfigValidationError(f'{field_name}[{index}] must be a string')
        text = item.strip()
        if not text:
            raise ConfigValidationError(f'{field_name}[{index}] cannot be empty')
        items.append(text)
    return tuple(items)


def expect_string_mapping(value: Any, *, field_name: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ConfigValidationError(f'{field_name} must be a table of strings')
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ConfigValidationError(f'{field_name} keys must be strings')
        if not isinstance(item, str):
            raise ConfigValidationError(f'{field_name}.{key} must be a string')
        result[str(key)] = item
    return result


__all__ = [
    'expect_bool',
    'expect_mapping',
    'expect_string',
    'expect_string_list',
    'expect_string_mapping',
]
