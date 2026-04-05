from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from ccbd.api_models import JobRecord

from ..base import ProviderRuntimeContext, ProviderSubmission
from .start import _session_selector_name


def resume_active_submission(
    job: JobRecord,
    submission: ProviderSubmission,
    *,
    context: ProviderRuntimeContext | None,
    load_session_fn: Callable[[Path, str], object | None],
    backend_for_session_fn: Callable[[dict], object | None],
    reader_factory: Callable[[object], object],
    configure_reader_fn: Callable[[object, dict[str, object], ProviderRuntimeContext], None] | None = None,
    completion_dir_fn: Callable[[object], str] | None = None,
) -> ProviderSubmission | None:
    if context is None or not context.workspace_path:
        return None

    state = dict(submission.runtime_state)
    if str(state.get("mode") or "passive") != "active":
        return None

    work_dir = Path(context.workspace_path).expanduser()
    session = load_session_fn(work_dir, agent_name=_session_selector_name(job))
    if session is None:
        return None
    ok, pane_or_err = session.ensure_pane()
    if not ok:
        return None

    backend = backend_for_session_fn(session.data)
    if backend is None:
        return None

    reader = reader_factory(session)
    if configure_reader_fn is not None:
        configure_reader_fn(reader, state, context)

    runtime_state = {
        **state,
        "reader": reader,
        "backend": backend,
        "pane_id": str(pane_or_err),
        "mode": "active",
        "session_path": state.get("session_path") or "",
    }
    if completion_dir_fn is not None:
        runtime_state["completion_dir"] = state.get("completion_dir") or completion_dir_fn(session)
    return replace(submission, runtime_state=runtime_state)


__all__ = ["resume_active_submission"]
