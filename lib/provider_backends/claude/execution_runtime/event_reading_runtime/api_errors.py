from __future__ import annotations


def terminal_api_error_payload(event: dict[str, object]) -> dict[str, object] | None:
    if not api_error_event(event):
        return None
    raw_entry = event.get("entry")
    if not isinstance(raw_entry, dict):
        return None
    retry_state = exhausted_retry_state(raw_entry)
    if retry_state is None:
        return None
    error_code, error_path = api_error_details(raw_entry)
    return {
        "message": build_api_error_message(error_code=error_code, error_path=error_path),
        "error_code": error_code,
        "error_path": error_path,
        "retry_attempt": retry_state[0],
        "max_retries": retry_state[1],
        "timestamp": str(raw_entry.get("timestamp") or ""),
    }


def api_error_event(event: dict[str, object]) -> bool:
    entry_type = str(event.get("entry_type") or "").strip().lower()
    subtype = str(event.get("subtype") or "").strip().lower()
    return entry_type == "system" and subtype == "api_error"


def exhausted_retry_state(raw_entry: dict[str, object]) -> tuple[int, int] | None:
    try:
        retry_attempt = int(raw_entry.get("retryAttempt"))
        max_retries = int(raw_entry.get("maxRetries"))
    except Exception:
        return None
    if max_retries <= 0 or retry_attempt < max_retries:
        return None
    return retry_attempt, max_retries


def api_error_details(raw_entry: dict[str, object]) -> tuple[str | None, str | None]:
    cause = raw_entry.get("cause")
    if not isinstance(cause, dict):
        cause = {}
    error_code = str(cause.get("code") or "").strip() or None
    error_path = str(cause.get("path") or "").strip() or None
    return error_code, error_path


def build_api_error_message(*, error_code: str | None, error_path: str | None) -> str:
    message_parts = ["Claude API request failed"]
    if error_code:
        message_parts.append(f"code={error_code}")
    if error_path:
        message_parts.append(f"path={error_path}")
    return " ".join(message_parts)


__all__ = [
    'api_error_details',
    'api_error_event',
    'build_api_error_message',
    'exhausted_retry_state',
    'terminal_api_error_payload',
]
