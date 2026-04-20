from __future__ import annotations

from provider_backends.codex.comm_runtime.polling_runtime.context import build_cursor, state_payload


def test_codex_polling_cursor_restores_last_rescan_from_state() -> None:
    state = state_payload(None, 0, last_rescan=12.5)

    cursor = build_cursor(state, timeout=0.0)

    assert cursor.offset == 0
    assert cursor.last_rescan == 12.5
