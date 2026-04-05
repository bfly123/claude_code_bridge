from __future__ import annotations

from pathlib import Path

from ccbd.api_models import JobRecord
from provider_core.protocol import request_anchor_for_job
from provider_execution.base import ProviderPollResult, ProviderRuntimeContext, ProviderSubmission
from provider_execution.common import request_anchor_from_runtime_state
from terminal_runtime import get_backend_for_session

from .comm import GeminiLogReader
from .execution_runtime import poll_submission as _poll_submission
from .execution_runtime import resume_submission as _resume_submission
from .execution_runtime import start_active_submission as _start_active_submission
from .protocol import (
    extract_reply_for_req,
    is_done_text,
    strip_done_text,
    wrap_gemini_prompt,
)
from .session import load_project_session


class GeminiProviderAdapter:
    provider = 'gemini'

    def start(self, job: JobRecord, *, context: ProviderRuntimeContext | None, now: str) -> ProviderSubmission:
        return _start_active_submission(
            self,
            job,
            context=context,
            now=now,
            load_session_fn=_load_session,
            backend_for_session_fn=get_backend_for_session,
            reader_factory=_reader_factory,
            request_anchor_fn=request_anchor_for_job,
            wrap_prompt_fn=wrap_gemini_prompt,
        )

    def poll(self, submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
        from .execution_runtime import polling as _polling

        _polling.extract_reply_for_req_fn = extract_reply_for_req
        _polling.is_done_text_fn = is_done_text
        _polling.strip_done_text_fn = strip_done_text
        return _poll_submission(submission, now=now)

    def export_runtime_state(self, submission: ProviderSubmission) -> dict[str, object]:
        return {
            'mode': submission.runtime_state.get('mode'),
            'state': submission.runtime_state.get('state') or {},
            'pane_id': submission.runtime_state.get('pane_id'),
            'request_anchor': request_anchor_from_runtime_state(submission.runtime_state, fallback=submission.job_id),
            'next_seq': submission.runtime_state.get('next_seq'),
            'anchor_emitted': submission.runtime_state.get('anchor_emitted'),
            'reply_buffer': submission.runtime_state.get('reply_buffer'),
            'session_path': submission.runtime_state.get('session_path'),
            'completion_dir': submission.runtime_state.get('completion_dir'),
        }

    def resume(
        self,
        job: JobRecord,
        submission: ProviderSubmission,
        *,
        context: ProviderRuntimeContext | None,
        persisted_state,
        now: str,
    ) -> ProviderSubmission | None:
        del persisted_state, now
        return _resume_submission(
            job,
            submission,
            context=context,
            load_session_fn=_load_session,
            backend_for_session_fn=get_backend_for_session,
            reader_factory=_reader_factory,
        )


def _load_session(work_dir: Path, *, agent_name: str):
    from .execution_runtime.start import load_session as _runtime_load_session

    return _runtime_load_session(load_project_session, work_dir, agent_name=agent_name)


def _reader_factory(session):
    return GeminiLogReader(work_dir=Path(session.work_dir))


def build_execution_adapter() -> GeminiProviderAdapter:
    return GeminiProviderAdapter()


__all__ = ['GeminiProviderAdapter', 'build_execution_adapter']
