from __future__ import annotations

import re

from ccb_protocol import DONE_PREFIX, REQ_ID_PREFIX, is_done_text, make_req_id, strip_done_text, wrap_codex_prompt
from ccb_protocol import strip_trailing_markers


def test_make_req_id_format_and_uniqueness() -> None:
    ids = [make_req_id() for _ in range(2000)]
    assert len(set(ids)) == len(ids)
    for rid in ids:
        assert isinstance(rid, str)
        assert len(rid) == 32
        assert re.fullmatch(r"[0-9a-f]{32}", rid) is not None


def test_wrap_codex_prompt_structure() -> None:
    req_id = make_req_id()
    message = "hello\nworld"
    prompt = wrap_codex_prompt(message, req_id)

    assert f"{REQ_ID_PREFIX} {req_id}" in prompt
    assert "IMPORTANT:" in prompt
    assert "- Reply normally." in prompt
    assert f"{DONE_PREFIX} {req_id}" in prompt
    assert prompt.endswith(f"{DONE_PREFIX} {req_id}\n")


def test_is_done_text_recognizes_last_nonempty_line() -> None:
    req_id = make_req_id()
    ok = f"hi\n{DONE_PREFIX} {req_id}\n"
    assert is_done_text(ok, req_id) is True

    ok_with_trailing_blanks = f"hi\n{DONE_PREFIX} {req_id}\n\n\n"
    assert is_done_text(ok_with_trailing_blanks, req_id) is True

    ok_with_trailing_harness_done = f"hi\n{DONE_PREFIX} {req_id}\nHARNESS_DONE\n"
    assert is_done_text(ok_with_trailing_harness_done, req_id) is True

    ok_with_trailing_harness_done_and_blanks = f"hi\n{DONE_PREFIX} {req_id}\n\nHARNESS_DONE\n\n"
    assert is_done_text(ok_with_trailing_harness_done_and_blanks, req_id) is True

    not_last = f"{DONE_PREFIX} {req_id}\nhi\n"
    assert is_done_text(not_last, req_id) is False

    other_id = make_req_id()
    wrong_id = f"hi\n{DONE_PREFIX} {other_id}\n"
    assert is_done_text(wrong_id, req_id) is False

    only_harness_done = "hi\nHARNESS_DONE\n"
    assert is_done_text(only_harness_done, req_id) is False


def test_strip_done_text_removes_done_line() -> None:
    req_id = make_req_id()
    text = f"line1\nline2\n{DONE_PREFIX} {req_id}\n\n"
    assert strip_done_text(text, req_id) == "line1\nline2"

    text_with_harness_done = f"line1\nline2\n{DONE_PREFIX} {req_id}\nHARNESS_DONE\n"
    assert strip_done_text(text_with_harness_done, req_id) == "line1\nline2"


def test_strip_trailing_markers_removes_done_and_harness_trailers() -> None:
    req_id = make_req_id()
    text = f"line1\nline2\n{DONE_PREFIX} {req_id}\nHARNESS_DONE\n\n"
    assert strip_trailing_markers(text) == "line1\nline2"
