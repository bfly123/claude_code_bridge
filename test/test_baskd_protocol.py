from __future__ import annotations

from ccb_protocol import DONE_PREFIX, REQ_ID_PREFIX, is_done_text, make_req_id
from baskd_protocol import wrap_codebuddy_prompt, extract_reply_for_req, BaskdRequest, BaskdResult


def test_wrap_codebuddy_prompt_structure() -> None:
    req_id = make_req_id()
    message = "hello\nworld"
    prompt = wrap_codebuddy_prompt(message, req_id)

    assert f"{REQ_ID_PREFIX} {req_id}" in prompt
    assert "IMPORTANT:" in prompt
    assert f"{DONE_PREFIX} {req_id}" in prompt
    assert prompt.endswith(f"{DONE_PREFIX} {req_id}\n")


def test_wrap_codebuddy_prompt_strips_trailing_whitespace() -> None:
    req_id = make_req_id()
    prompt = wrap_codebuddy_prompt("  test  \n\n", req_id)
    # Message should be rstripped
    assert "  test" in prompt


def test_extract_reply_for_req_basic() -> None:
    req_id = make_req_id()
    text = f"some preamble\nCCB_DONE: {req_id}\n"
    reply = extract_reply_for_req(text, req_id)
    assert "some preamble" in reply


def test_extract_reply_for_req_empty_on_wrong_id() -> None:
    req_id = make_req_id()
    other_id = make_req_id()
    text = f"content\nCCB_DONE: {other_id}\n"
    reply = extract_reply_for_req(text, req_id)
    assert reply == ""


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
    reply = extract_reply_for_req(text, req_id)
    # With no done markers at all, should return stripped text
    assert "just some plain text" in reply


def test_baskd_request_dataclass() -> None:
    req = BaskdRequest(
        client_id="client-1",
        work_dir="/tmp/test",
        timeout_s=60.0,
        quiet=False,
        message="hello",
    )
    assert req.client_id == "client-1"
    assert req.caller == "claude"  # default
    assert req.req_id is None
    assert req.output_path is None


def test_baskd_result_dataclass() -> None:
    result = BaskdResult(
        exit_code=0,
        reply="test reply",
        req_id="abc123",
        session_key="codebuddy:xyz",
        done_seen=True,
        done_ms=1500,
    )
    assert result.exit_code == 0
    assert result.done_seen is True
    assert result.anchor_seen is False  # default
    assert result.fallback_scan is False  # default
