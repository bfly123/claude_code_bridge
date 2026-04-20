from __future__ import annotations


def retry_failure_detail(decision) -> str:
    parts = detail_parts(decision)
    return ', '.join(parts) or 'reason=api_error'


def detail_parts(decision) -> list[str]:
    diagnostics = getattr(decision, 'diagnostics', {}) or {}
    parts: list[str] = []
    append_detail(parts, 'reason', getattr(decision, 'reason', ''))
    append_detail(parts, 'error_type', diagnostics.get('error_type'))
    append_detail(parts, 'error_code', diagnostics.get('error_code'))
    append_detail(parts, 'error_message', error_message(diagnostics))
    append_detail(parts, 'fault_rule_id', diagnostics.get('fault_rule_id'))
    return parts


def append_detail(parts: list[str], key: str, value: object) -> None:
    text = str(value or '').strip()
    if text:
        parts.append(f'{key}={text}')


def error_message(diagnostics: dict) -> str:
    return str(
        diagnostics.get('error_message')
        or diagnostics.get('fault_message')
        or diagnostics.get('error')
        or ''
    ).strip()


__all__ = ['retry_failure_detail']
