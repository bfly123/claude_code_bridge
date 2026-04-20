from __future__ import annotations

from provider_backends.droid.protocol import DroidRequest, DroidResult, extract_reply_for_req, wrap_droid_prompt
from provider_core.protocol import DONE_PREFIX, REQ_ID_PREFIX, make_req_id


def test_wrap_droid_prompt_structure() -> None:
    req_id = make_req_id()
    prompt = wrap_droid_prompt("hello\nworld", req_id)

    assert f"{REQ_ID_PREFIX} {req_id}" in prompt
    assert "IMPORTANT:" in prompt
    assert f"{DONE_PREFIX} {req_id}" in prompt
    assert prompt.endswith(f"{DONE_PREFIX} {req_id}\n")


def test_extract_reply_for_req_returns_last_target_window() -> None:
    req1 = make_req_id()
    req2 = make_req_id()
    text = (
        f"reply1\nCCB_DONE: {req1}\n"
        f"\nreply2\nline2\nCCB_DONE: {req2}\n"
    )

    assert extract_reply_for_req(text, req2) == "reply2\nline2"


def test_droid_request_and_result_defaults() -> None:
    request = DroidRequest(
        client_id="client-1",
        work_dir="/tmp/project",
        timeout_s=30.0,
        quiet=False,
        message="run",
    )
    result = DroidResult(
        exit_code=0,
        reply="ok",
        req_id="req-1",
        session_key="droid:1",
        done_seen=True,
    )

    assert request.caller == "claude"
    assert request.req_id is None
    assert result.anchor_seen is False
    assert result.fallback_scan is False
