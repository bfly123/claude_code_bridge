from __future__ import annotations

from provider_backends.copilot.protocol import (
    CopilotRequest,
    CopilotResult,
    extract_reply_for_req,
    wrap_copilot_prompt,
)
from provider_core.protocol import DONE_PREFIX, REQ_ID_PREFIX, make_req_id


def test_wrap_copilot_prompt_structure() -> None:
    req_id = make_req_id()
    message = "hello\nworld"
    prompt = wrap_copilot_prompt(message, req_id)

    assert f"{REQ_ID_PREFIX} {req_id}" in prompt
    assert "IMPORTANT:" in prompt
    assert f"{DONE_PREFIX} {req_id}" in prompt
    assert prompt.endswith(f"{DONE_PREFIX} {req_id}\n")


def test_wrap_copilot_prompt_strips_trailing_whitespace() -> None:
    req_id = make_req_id()
    prompt = wrap_copilot_prompt("  test  \n\n", req_id)

    assert "  test" in prompt


def test_extract_reply_for_req_basic() -> None:
    req_id = make_req_id()
    text = f"some preamble\nCCB_DONE: {req_id}\n"

    assert "some preamble" in extract_reply_for_req(text, req_id)


def test_extract_reply_for_req_empty_on_wrong_id() -> None:
    req_id = make_req_id()
    other_id = make_req_id()
    text = f"content\nCCB_DONE: {other_id}\n"

    assert extract_reply_for_req(text, req_id) == ""


def test_extract_reply_for_req_multiple_done_markers() -> None:
    req1 = make_req_id()
    req2 = make_req_id()
    text = (
        f"reply1\nCCB_DONE: {req1}\n"
        f"reply2\nCCB_DONE: {req2}\n"
    )

    reply = extract_reply_for_req(text, req2)
    assert "reply2" in reply
    assert "reply1" not in reply


def test_extract_reply_for_req_no_markers() -> None:
    req_id = make_req_id()
    text = "just some plain text without markers"

    assert "just some plain text" in extract_reply_for_req(text, req_id)


def test_copilot_request_dataclass() -> None:
    req = CopilotRequest(
        client_id="client-1",
        work_dir="/tmp/test",
        timeout_s=60.0,
        quiet=False,
        message="hello",
    )

    assert req.client_id == "client-1"
    assert req.caller == "claude"
    assert req.req_id is None


def test_copilot_result_dataclass() -> None:
    result = CopilotResult(
        exit_code=0,
        reply="test reply",
        req_id="abc123",
        session_key="copilot:xyz",
        done_seen=True,
        done_ms=1500,
    )

    assert result.exit_code == 0
    assert result.done_seen is True
    assert result.anchor_seen is False
    assert result.fallback_scan is False
