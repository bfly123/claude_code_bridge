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
    state = dict(submission.runtime_state)
    work_dir = _active_work_dir(context, state)
    if work_dir is None:
        return None

    prepared = _resume_prepared_session(job, work_dir, load_session_fn=load_session_fn)
    if prepared is None:
        return None
    session, pane_id = prepared

    backend = backend_for_session_fn(session.data)
    if backend is None:
        return None

    reader = reader_factory(session)
    if configure_reader_fn is not None:
        configure_reader_fn(reader, state, context)

    runtime_state = _resumed_runtime_state(
        state,
        reader=reader,
        backend=backend,
        pane_id=pane_id,
        session=session,
        completion_dir_fn=completion_dir_fn,
    )
    return replace(submission, runtime_state=runtime_state)


def _active_work_dir(
    context: ProviderRuntimeContext | None,
    state: dict[str, object],
) -> Path | None:
    if context is None or not context.workspace_path:
        return None
    if str(state.get("mode") or "passive") != "active":
        return None
    return Path(context.workspace_path).expanduser()


def _resume_prepared_session(
    job: JobRecord,
    work_dir: Path,
    *,
    load_session_fn: Callable[[Path, str], object | None],
) -> tuple[object, str] | None:
    session = load_session_fn(work_dir, agent_name=_session_selector_name(job))
    if session is None:
        return None
    ok, pane_or_err = session.ensure_pane()
    if not ok:
        return None
    return session, str(pane_or_err)


def _resumed_runtime_state(
    state: dict[str, object],
    *,
    reader: object,
    backend: object,
    pane_id: str,
    session: object,
    completion_dir_fn: Callable[[object], str] | None,
) -> dict[str, object]:
    runtime_state = {
        **state,
        "reader": reader,
        "backend": backend,
        "pane_id": pane_id,
        "mode": "active",
        "session_path": state.get("session_path") or "",
    }
    if completion_dir_fn is not None:
        runtime_state["completion_dir"] = state.get("completion_dir") or completion_dir_fn(session)
    return runtime_state


__all__ = ["resume_active_submission"]
