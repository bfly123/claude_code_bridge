from __future__ import annotations

from pathlib import Path

from ccbd.api_models import JobRecord
from provider_core.protocol import request_anchor_for_job, wrap_codex_turn_prompt
from provider_execution.base import ProviderPollResult, ProviderRuntimeContext, ProviderSubmission
from provider_execution.common import request_anchor_from_runtime_state
from terminal_runtime import get_backend_for_session

from .comm import CodexLogReader
from .execution_runtime import poll_submission as _poll_submission
from .execution_runtime import resume_submission as _resume_submission
from .execution_runtime import start_active_submission as _start_active_submission
from .session import load_project_session
from .session_runtime.follow_policy import codex_session_root_path, should_follow_workspace_sessions


class CodexProviderAdapter:
    provider = 'codex'

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
            wrap_prompt_fn=wrap_codex_turn_prompt,
        )

    def poll(self, submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
        return _poll_submission(submission, now=now)

    def export_runtime_state(self, submission: ProviderSubmission) -> dict[str, object]:
        return {
            'mode': submission.runtime_state.get('mode'),
            'state': submission.runtime_state.get('state') or {},
            'pane_id': submission.runtime_state.get('pane_id'),
            'request_anchor': request_anchor_from_runtime_state(submission.runtime_state, fallback=submission.job_id),
            'next_seq': submission.runtime_state.get('next_seq'),
            'anchor_seen': submission.runtime_state.get('anchor_seen'),
            'no_wrap': submission.runtime_state.get('no_wrap'),
            'bound_turn_id': submission.runtime_state.get('bound_turn_id'),
            'bound_task_id': submission.runtime_state.get('bound_task_id'),
            'reply_buffer': submission.runtime_state.get('reply_buffer'),
            'last_agent_message': submission.runtime_state.get('last_agent_message'),
            'last_final_answer': submission.runtime_state.get('last_final_answer'),
            'last_assistant_message': submission.runtime_state.get('last_assistant_message'),
            'last_assistant_signature': submission.runtime_state.get('last_assistant_signature'),
            'session_path': submission.runtime_state.get('session_path'),
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


def _reader_factory(session, preferred_log: Path | None):
    work_dir = Path(session.work_dir)
    kwargs: dict[str, object] = {
        "log_path": preferred_log if preferred_log is not None else (Path(session.codex_session_path).expanduser() if session.codex_session_path else None),
        "session_id_filter": session.codex_session_id or None,
        "work_dir": work_dir,
        "follow_workspace_sessions": should_follow_workspace_sessions(
            work_dir=work_dir,
            session_file=getattr(session, "session_file", None),
            session_data=getattr(session, "data", None),
        ),
    }
    session_root = codex_session_root_path(getattr(session, "data", None))
    if session_root is not None:
        kwargs["root"] = session_root
    return CodexLogReader(**kwargs)


def _load_session(work_dir: Path, agent_name: str):
    from .execution_runtime.start import load_session as _runtime_load_session

    return _runtime_load_session(load_project_session, work_dir, agent_name=agent_name)


def build_execution_adapter() -> CodexProviderAdapter:
    return CodexProviderAdapter()


__all__ = ['CodexProviderAdapter', 'build_execution_adapter']
