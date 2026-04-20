from __future__ import annotations

from .result import pane_dead_result, runtime_error_result
from ..models import PreparedActivePoll
from ...base import ProviderPollResult, ProviderSubmission
from ...common import is_runtime_target_alive


def prepare_active_poll(submission: ProviderSubmission, *, now: str) -> ProviderPollResult | PreparedActivePoll | None:
    return _prepare_active_poll(submission, now=now, check_pane_alive=True)


def prepare_active_poll_without_liveness(
    submission: ProviderSubmission,
    *,
    now: str,
) -> ProviderPollResult | PreparedActivePoll | None:
    return _prepare_active_poll(submission, now=now, check_pane_alive=False)


def _prepare_active_poll(
    submission: ProviderSubmission,
    *,
    now: str,
    check_pane_alive: bool,
) -> ProviderPollResult | PreparedActivePoll | None:
    runtime_error = runtime_mode_error(submission, now=now)
    if runtime_error is not None:
        return runtime_error

    reader = submission.runtime_state.get("reader")
    backend = submission.runtime_state.get("backend")
    pane_id = str(submission.runtime_state.get("pane_id") or "")
    if reader is None or backend is None or not pane_id:
        return runtime_error_result(
            submission,
            now=now,
            reason="runtime_state_corrupt",
        )

    if check_pane_alive:
        result = ensure_active_pane_alive(submission, backend=backend, pane_id=pane_id, now=now)
        if result is not None:
            return result

    return PreparedActivePoll(reader=reader, backend=backend, pane_id=pane_id)


def runtime_mode_error(submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
    mode = str(submission.runtime_state.get("mode") or "passive")
    if mode == "passive":
        return runtime_error_result(
            submission,
            now=now,
            reason=str(submission.runtime_state.get("reason") or "runtime_unavailable"),
            error=str(submission.runtime_state.get("error") or ""),
        )
    if mode == "error":
        return runtime_error_result(
            submission,
            now=now,
            reason=str(submission.runtime_state.get("reason") or "transport_error"),
            error=str(submission.runtime_state.get("error") or ""),
        )
    return None


def ensure_active_pane_alive(
    submission: ProviderSubmission,
    *,
    backend: object,
    pane_id: str,
    now: str,
) -> ProviderPollResult | None:
    try:
        pane_alive = is_runtime_target_alive(backend, pane_id)
    except Exception:
        pane_alive = False
    if pane_alive:
        return None
    return pane_dead_result(submission, now=now)


__all__ = [
    "ensure_active_pane_alive",
    "prepare_active_poll",
    "prepare_active_poll_without_liveness",
]
