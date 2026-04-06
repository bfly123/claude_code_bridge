from __future__ import annotations


def clean_text(value: object) -> str | None:
    text = str(value or '').strip()
    return text or None


def clean_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def coerce_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not text.isdigit():
        raise ValueError(f'invalid integer value: {value!r}')
    number = int(text)
    return number if number > 0 else None


def to_runtime_state(value: object) -> str | None:
    if value is None:
        return None
    return clean_text(getattr(value, 'value', value))


__all__ = ['clean_text', 'clean_tuple', 'coerce_int', 'to_runtime_state']
