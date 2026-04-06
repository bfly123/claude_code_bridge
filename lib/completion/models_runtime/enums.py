from __future__ import annotations

from enum import Enum


SCHEMA_VERSION = 2


class CompletionValidationError(ValueError):
    pass


class CompletionStatus(str, Enum):
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    FAILED = 'failed'
    INCOMPLETE = 'incomplete'


class CompletionConfidence(str, Enum):
    EXACT = 'exact'
    OBSERVED = 'observed'
    DEGRADED = 'degraded'


class CompletionFamily(str, Enum):
    PROTOCOL_TURN = 'protocol_turn'
    STRUCTURED_RESULT = 'structured_result'
    SESSION_BOUNDARY = 'session_boundary'
    ANCHORED_SESSION_STABILITY = 'anchored_session_stability'
    TERMINAL_TEXT_QUIET = 'terminal_text_quiet'


class CompletionSourceKind(str, Enum):
    PROTOCOL_EVENT_STREAM = 'protocol_event_stream'
    STRUCTURED_RESULT_STREAM = 'structured_result_stream'
    SESSION_EVENT_LOG = 'session_event_log'
    SESSION_SNAPSHOT = 'session_snapshot'
    TERMINAL_TEXT = 'terminal_text'


class SelectorFamily(str, Enum):
    FINAL_MESSAGE = 'final_message'
    STRUCTURED_RESULT = 'structured_result'
    SESSION_REPLY = 'session_reply'


class CompletionItemKind(str, Enum):
    ANCHOR_SEEN = 'anchor_seen'
    ASSISTANT_CHUNK = 'assistant_chunk'
    ASSISTANT_FINAL = 'assistant_final'
    TOOL_CALL = 'tool_call'
    TOOL_RESULT = 'tool_result'
    RESULT = 'result'
    TURN_BOUNDARY = 'turn_boundary'
    TURN_ABORTED = 'turn_aborted'
    CANCEL_INFO = 'cancel_info'
    ERROR = 'error'
    PANE_DEAD = 'pane_dead'
    SESSION_SNAPSHOT = 'session_snapshot'
    SESSION_MUTATION = 'session_mutation'
    SESSION_ROTATE = 'session_rotate'


class ReplyCandidateKind(str, Enum):
    LAST_AGENT_MESSAGE = 'last_agent_message'
    FINAL_ANSWER = 'final_answer'
    ASSISTANT_FINAL = 'assistant_final'
    ASSISTANT_CHUNK_MERGED = 'assistant_chunk_merged'
    SESSION_REPLY = 'session_reply'
    FALLBACK_TEXT = 'fallback_text'


REPLY_PRIORITY = {
    ReplyCandidateKind.LAST_AGENT_MESSAGE: 2,
    ReplyCandidateKind.FINAL_ANSWER: 3,
    ReplyCandidateKind.ASSISTANT_FINAL: 4,
    ReplyCandidateKind.ASSISTANT_CHUNK_MERGED: 5,
    ReplyCandidateKind.SESSION_REPLY: 6,
    ReplyCandidateKind.FALLBACK_TEXT: 7,
}
