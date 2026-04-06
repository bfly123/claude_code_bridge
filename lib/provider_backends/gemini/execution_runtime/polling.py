from __future__ import annotations

from .polling_runtime import clean_reply as _clean_reply_impl
from .polling_runtime import int_or_none as _int_or_none_impl
from .polling_runtime import poll_exact_hook as _poll_exact_hook_impl
from .polling_runtime import poll_submission as _poll_submission_impl


def poll_submission(submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
    return _poll_submission_impl(
        submission,
        now=now,
        extract_reply_for_req_fn=extract_reply_for_req_fn,
        is_done_text_fn=is_done_text_fn,
        strip_done_text_fn=strip_done_text_fn,
    )


def clean_reply(reply: str, *, req_id: str) -> str:
    return _clean_reply_impl(
        reply,
        req_id=req_id,
        extract_reply_for_req_fn=extract_reply_for_req_fn,
        is_done_text_fn=is_done_text_fn,
        strip_done_text_fn=strip_done_text_fn,
    )


def int_or_none(value: object) -> int | None:
    return _int_or_none_impl(value)


def poll_exact_hook(submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
    return _poll_exact_hook_impl(submission, now=now)


extract_reply_for_req_fn = None
is_done_text_fn = None
strip_done_text_fn = None


__all__ = [
    'clean_reply',
    'int_or_none',
    'poll_exact_hook',
    'poll_submission',
]
