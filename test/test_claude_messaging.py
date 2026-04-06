from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from provider_backends.claude.comm_runtime.communicator_runtime.messaging import ask_sync


def test_ask_sync_waits_for_done_and_remembers_session() -> None:
    remembered: list[Path] = []
    waits = iter(
        [
            (None, {"cursor": 1}),
            ("reply body\nCCB_DONE: req-1", {"cursor": 2}),
        ]
    )
    comm = SimpleNamespace(
        timeout=5,
        log_reader=SimpleNamespace(
            capture_state=lambda: {"cursor": 0},
            wait_for_message=lambda state, timeout: next(waits),
            current_session_path=lambda: Path("/tmp/claude-session.jsonl"),
        ),
        _check_session_health_impl=lambda probe_terminal=False: (True, "ok"),
        _send_via_terminal=lambda text: None,
        _remember_claude_session=lambda path: remembered.append(path),
    )

    reply = ask_sync(
        comm,
        "hello",
        req_id_factory=lambda: "req-1",
        wrap_prompt_fn=lambda question, req_id: f"{question}::{req_id}",
        is_done_text_fn=lambda text, req_id: f"CCB_DONE: {req_id}" in text,
        strip_done_text_fn=lambda text, req_id: text.replace(f"CCB_DONE: {req_id}", "").strip(),
    )

    assert reply == "reply body"
    assert remembered == [Path("/tmp/claude-session.jsonl")]
