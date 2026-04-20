from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from .enums import CompletionItemKind, ReplyCandidateKind
from .records import CompletionItem, ReplyCandidate


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def parse_timestamp(value: str) -> datetime:
    normalized = value.replace('Z', '+00:00')
    return datetime.fromisoformat(normalized)


def seconds_between(start: str, end: str) -> float:
    return (parse_timestamp(end) - parse_timestamp(start)).total_seconds()


def fingerprint_text(*parts: Any) -> str:
    digest = sha256()
    for part in parts:
        digest.update(str(part).encode('utf-8'))
        digest.update(b'\x1f')
    return digest.hexdigest()


def first_non_empty(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def reply_candidates_from_item(item: CompletionItem) -> tuple[ReplyCandidate, ...]:
    candidates: list[ReplyCandidate] = []
    payload = item.payload
    provider_turn_ref = first_non_empty(payload, 'turn_id', 'provider_turn_ref', 'message_id', 'session_id')

    explicit_last = first_non_empty(payload, 'last_agent_message')
    if explicit_last:
        candidates.append(
            ReplyCandidate(
                kind=ReplyCandidateKind.LAST_AGENT_MESSAGE,
                text=explicit_last,
                timestamp=item.timestamp,
                provider_turn_ref=provider_turn_ref,
                priority=None,
                cursor=item.cursor,
            )
        )

    if item.kind is CompletionItemKind.RESULT:
        final_text = first_non_empty(payload, 'reply', 'result_text', 'final_answer', 'text')
        if final_text:
            candidates.append(
                ReplyCandidate(
                    kind=ReplyCandidateKind.FINAL_ANSWER,
                    text=final_text,
                    timestamp=item.timestamp,
                    provider_turn_ref=provider_turn_ref,
                    priority=None,
                    cursor=item.cursor,
                )
            )

    if item.kind is CompletionItemKind.ASSISTANT_FINAL:
        final_text = first_non_empty(payload, 'text', 'reply')
        if final_text:
            candidates.append(
                ReplyCandidate(
                    kind=ReplyCandidateKind.ASSISTANT_FINAL,
                    text=final_text,
                    timestamp=item.timestamp,
                    provider_turn_ref=provider_turn_ref,
                    priority=None,
                    cursor=item.cursor,
                )
            )

    if item.kind is CompletionItemKind.ASSISTANT_CHUNK:
        merged_text = first_non_empty(payload, 'merged_text', 'text', 'reply')
        if merged_text:
            candidates.append(
                ReplyCandidate(
                    kind=ReplyCandidateKind.ASSISTANT_CHUNK_MERGED,
                    text=merged_text,
                    timestamp=item.timestamp,
                    provider_turn_ref=provider_turn_ref,
                    priority=None,
                    cursor=item.cursor,
                )
            )

    if item.kind in {CompletionItemKind.SESSION_SNAPSHOT, CompletionItemKind.SESSION_MUTATION}:
        session_text = first_non_empty(payload, 'reply', 'content', 'text')
        if session_text:
            candidates.append(
                ReplyCandidate(
                    kind=ReplyCandidateKind.SESSION_REPLY,
                    text=session_text,
                    timestamp=item.timestamp,
                    provider_turn_ref=provider_turn_ref,
                    priority=None,
                    cursor=item.cursor,
                )
            )

    fallback_text = first_non_empty(payload, 'fallback_text')
    if fallback_text:
        candidates.append(
            ReplyCandidate(
                kind=ReplyCandidateKind.FALLBACK_TEXT,
                text=fallback_text,
                timestamp=item.timestamp,
                provider_turn_ref=provider_turn_ref,
                priority=None,
                cursor=item.cursor,
            )
        )

    return tuple(candidates)
