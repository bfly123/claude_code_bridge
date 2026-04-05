from __future__ import annotations

from completion.detectors.anchored_session_stability import AnchoredSessionStabilityDetector
from completion.detectors.base import CompletionDetector
from completion.detectors.legacy_text_quiet import LegacyTextQuietDetector
from completion.detectors.protocol_turn import ProtocolTurnDetector
from completion.detectors.session_boundary import SessionBoundaryDetector
from completion.detectors.structured_result import StructuredResultDetector
from completion.models import CompletionFamily, CompletionProfile, SelectorFamily
from completion.profiles import CompletionManifest, build_completion_profile
from completion.selectors.base import ReplySelector
from completion.selectors.final_message import FinalMessageSelector
from completion.selectors.session_reply import SessionReplySelector
from completion.selectors.structured_result import StructuredResultSelector


class CompletionRegistry:
    def build_profile(self, agent_spec, runtime_ref, provider_manifest: CompletionManifest) -> CompletionProfile:
        del runtime_ref
        return build_completion_profile(agent_spec, provider_manifest)

    def build_detector(self, profile: CompletionProfile) -> CompletionDetector:
        mapping = {
            CompletionFamily.PROTOCOL_TURN: ProtocolTurnDetector,
            CompletionFamily.STRUCTURED_RESULT: StructuredResultDetector,
            CompletionFamily.SESSION_BOUNDARY: SessionBoundaryDetector,
            CompletionFamily.ANCHORED_SESSION_STABILITY: AnchoredSessionStabilityDetector,
            CompletionFamily.LEGACY_TEXT_QUIET: LegacyTextQuietDetector,
        }
        return mapping[profile.completion_family]()

    def build_selector(self, profile: CompletionProfile) -> ReplySelector:
        mapping = {
            SelectorFamily.FINAL_MESSAGE: FinalMessageSelector,
            SelectorFamily.STRUCTURED_RESULT: StructuredResultSelector,
            SelectorFamily.SESSION_REPLY: SessionReplySelector,
        }
        return mapping[profile.selector_family]()
