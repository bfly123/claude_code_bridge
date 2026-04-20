from __future__ import annotations


def normalize_expected_user_options(service, expected: dict[str, str]) -> list[tuple[str, str]]:
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name, value in dict(expected or {}).items():
        opt = service.normalize_user_option_fn(str(name))
        text = str(value or '').strip()
        if not opt or not text or opt in seen:
            continue
        seen.add(opt)
        normalized.append((opt, text))
    return normalized


def normalize_user_option_names(service, user_options: tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for name in tuple(user_options or ()):
        opt = service.normalize_user_option_fn(str(name))
        if not opt or opt in seen:
            continue
        seen.add(opt)
        normalized.append(opt)
    return normalized


def pane_matches_expected(parts: list[str], normalized: list[tuple[str, str]]) -> bool:
    for index, (_, expected_value) in enumerate(normalized, start=1):
        if (parts[index] or '').strip() != expected_value:
            return False
    return True


__all__ = ['normalize_expected_user_options', 'normalize_user_option_names', 'pane_matches_expected']
