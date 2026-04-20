from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from agents.models import ProjectConfig, RuntimeMode
from ccbd.api_models import JobRecord, TargetKind
from completion.detectors.base import CompletionDetector
from completion.models import (
    CompletionCursor,
    CompletionDecision,
    CompletionItemKind,
    CompletionRequestContext,
    CompletionState,
    seconds_between,
    reply_candidates_from_item,
)
from completion.registry import CompletionRegistry
from completion.selectors.base import ReplySelector
from provider_core.catalog import ProviderCatalog

_DEFAULT_REQUEST_TIMEOUT_S = 3600.0
_DISABLED_REQUEST_BINDING_TIMEOUT_S = 315360000.0


@dataclass
class _ActiveTracker:
    agent_name: str
    detector: CompletionDetector
    selector: ReplySelector
    started_at: str
    timeout_s: float


@dataclass(frozen=True)
class CompletionTrackerView:
    job_id: str
    agent_name: str
    state: CompletionState
    decision: CompletionDecision


class CompletionTrackerService:
    def __init__(
        self,
        config: ProjectConfig,
        provider_catalog: ProviderCatalog,
        registry: CompletionRegistry | None = None,
        *,
        request_timeout_s: float = _DEFAULT_REQUEST_TIMEOUT_S,
    ) -> None:
        self._config = config
        self._provider_catalog = provider_catalog
        self._registry = registry or CompletionRegistry()
        self._request_timeout_s = request_timeout_s
        self._trackers: dict[str, _ActiveTracker] = {}

    def start(self, job: JobRecord, *, started_at: str) -> CompletionTrackerView:
        if job.target_kind is TargetKind.AGENT:
            spec = self._config.agents[job.agent_name]
            manifest = self._provider_catalog.resolve_completion_manifest(spec.provider, spec.runtime_mode)
            tracker_name = job.agent_name
        else:
            spec = SimpleNamespace(provider=job.provider, runtime_mode=RuntimeMode.PANE_BACKED)
            manifest = self._provider_catalog.resolve_completion_manifest(job.provider, RuntimeMode.PANE_BACKED)
            tracker_name = job.agent_name or job.provider
        profile = self._registry.build_profile(spec, None, manifest)
        detector = self._registry.build_detector(profile)
        selector = self._registry.build_selector(profile)
        binding_timeout_s = self._request_timeout_s if self._request_timeout_s > 0 else _DISABLED_REQUEST_BINDING_TIMEOUT_S
        detector.bind(
            CompletionRequestContext(
                req_id=job.job_id,
                agent_name=tracker_name,
                provider=job.provider,
                timeout_s=binding_timeout_s,
            ),
            CompletionCursor(
                source_kind=profile.completion_source_kind,
                event_seq=0,
                updated_at=started_at,
            ),
        )
        self._trackers[job.job_id] = _ActiveTracker(
            agent_name=tracker_name,
            detector=detector,
            selector=selector,
            started_at=started_at,
            timeout_s=self._request_timeout_s,
        )
        return self.current(job.job_id)

    def current(self, job_id: str) -> CompletionTrackerView | None:
        tracker = self._trackers.get(job_id)
        if tracker is None:
            return None
        decision = tracker.detector.decision()
        reply = tracker.selector.select(decision) if decision.terminal else tracker.selector.preview()
        if reply and not decision.reply:
            decision = decision.with_reply(reply)
        return CompletionTrackerView(
            job_id=job_id,
            agent_name=tracker.agent_name,
            state=tracker.detector.state(),
            decision=decision,
        )

    def ingest(self, job_id: str, item) -> CompletionTrackerView:
        tracker = self._require(job_id)
        if item.kind is CompletionItemKind.SESSION_ROTATE:
            tracker.selector.reset()
        for candidate in reply_candidates_from_item(item):
            tracker.selector.ingest_candidate(candidate)
        tracker.detector.ingest(item)
        current = self.current(job_id)
        assert current is not None
        return current

    def tick(self, job_id: str, *, now: str) -> CompletionTrackerView:
        tracker = self._require(job_id)
        if hasattr(tracker.detector, 'tick'):
            tracker.detector.tick(now, tracker.detector.state().latest_cursor)
        self._maybe_finalize_timeout(tracker, now=now)
        current = self.current(job_id)
        assert current is not None
        return current

    def tick_all(self, *, now: str) -> tuple[CompletionTrackerView, ...]:
        return tuple(self.tick(job_id, now=now) for job_id in tuple(self._trackers))

    def finish(self, job_id: str) -> None:
        self._trackers.pop(job_id, None)

    def _require(self, job_id: str) -> _ActiveTracker:
        try:
            return self._trackers[job_id]
        except KeyError as exc:
            raise KeyError(f'unknown completion tracker: {job_id}') from exc

    def _maybe_finalize_timeout(self, tracker: _ActiveTracker, *, now: str) -> None:
        if tracker.timeout_s <= 0:
            return
        if not hasattr(tracker.detector, 'finalize_timeout'):
            return
        if tracker.detector.decision().terminal:
            return
        try:
            elapsed_s = seconds_between(tracker.started_at, now)
        except Exception:
            return
        if elapsed_s < tracker.timeout_s:
            return
        tracker.detector.finalize_timeout(now, tracker.detector.state().latest_cursor)
