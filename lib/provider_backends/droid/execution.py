from __future__ import annotations

from pathlib import Path

from ccbd.api_models import JobRecord
from provider_core.protocol import request_anchor_for_job
from provider_execution.base import ProviderPollResult, ProviderRuntimeContext, ProviderSubmission
from terminal_runtime import get_backend_for_session

from .comm import DroidLogReader
from .execution_runtime import poll_submission as _poll_submission_impl
from .execution_runtime import start_submission as _start_submission_impl
from .execution_runtime.helpers import clean_reply as _clean_reply_impl
from .execution_runtime.helpers import load_session as _load_session_impl
from .execution_runtime.helpers import state_session_path as _state_session_path_impl
from .protocol import extract_reply_for_req, is_done_text, strip_done_text, wrap_droid_prompt
from .session import load_project_session


class DroidProviderAdapter:
    provider = "droid"

    def restore_diagnostics(self) -> dict[str, object]:
        return {
            "resume_supported": False,
            "restore_mode": "resubmit_required",
            "restore_reason": "provider_resume_unsupported",
            "restore_detail": "droid live polling works, but restart-time execution resume is not implemented yet",
        }

    def start(self, job: JobRecord, *, context: ProviderRuntimeContext | None, now: str) -> ProviderSubmission:
        return _start_submission_impl(
            job,
            context=context,
            now=now,
            provider=self.provider,
            load_session_fn=_load_session,
            backend_for_session_fn=get_backend_for_session,
            reader_cls=DroidLogReader,
            request_anchor_fn=request_anchor_for_job,
            wrap_prompt_fn=wrap_droid_prompt,
        )

    def poll(self, submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
        return _poll_submission_impl(
            submission,
            now=now,
            state_session_path_fn=_state_session_path,
            is_done_text_fn=is_done_text,
            clean_reply_fn=_clean_reply,
        )


def _load_session(work_dir: Path, *, agent_name: str):
    return _load_session_impl(work_dir, agent_name=agent_name, primary_agent="droid", load_project_session_fn=load_project_session)


def _state_session_path(state: dict[str, object]) -> str:
    return _state_session_path_impl(state)


def _clean_reply(text: str, *, req_id: str) -> str:
    return _clean_reply_impl(
        text,
        req_id=req_id,
        is_done_text_fn=is_done_text,
        extract_reply_for_req_fn=extract_reply_for_req,
        strip_done_text_fn=strip_done_text,
    )


def build_execution_adapter() -> DroidProviderAdapter:
    return DroidProviderAdapter()


__all__ = ["DroidProviderAdapter", "build_execution_adapter"]
