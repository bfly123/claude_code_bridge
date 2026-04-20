from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from provider_core.session_binding_runtime import find_bound_session_file

from memory.types import ConversationEntry, SessionNotFoundError, SessionStats, TransferContext


def load_session_data(
    work_dir: Path,
    source_session_files: dict[str, str],
    provider: str,
) -> tuple[Optional[Path], dict]:
    filename = source_session_files.get(provider)
    if not filename:
        return None, {}
    session_file = find_bound_session_file(
        provider=provider,
        base_filename=filename,
        work_dir=work_dir,
    )
    if not session_file or not session_file.exists():
        return None, {}
    try:
        raw = session_file.read_text(encoding="utf-8-sig", errors="replace")
        data = json.loads(raw)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    return session_file, data


def auto_source_candidates(
    work_dir: Path,
    default_source_order: tuple[str, ...],
    source_session_files: dict[str, str],
) -> list[str]:
    candidates: list[tuple[float, str]] = []
    for provider in default_source_order:
        filename = source_session_files.get(provider)
        if not filename:
            continue
        session_file = find_bound_session_file(
            provider=provider,
            base_filename=filename,
            work_dir=work_dir,
        )
        if not session_file or not session_file.exists():
            continue
        try:
            mtime = session_file.stat().st_mtime
        except OSError:
            mtime = 0.0
        candidates.append((mtime, provider))
    ordered = [provider for _, provider in sorted(candidates, key=lambda item: item[0], reverse=True)]
    for provider in default_source_order:
        if provider not in ordered:
            ordered.append(provider)
    return ordered


def context_from_pairs(
    *,
    deduper,
    formatter,
    max_tokens: int,
    pairs: list[tuple[str, str]],
    provider: str,
    session_id: str,
    session_path: Optional[Path] = None,
    last_n: int = 3,
    stats: Optional[SessionStats] = None,
) -> TransferContext:
    cleaned_pairs: list[tuple[str, str]] = []
    prev_hash: Optional[str] = None
    for user_msg, assistant_msg in pairs:
        cleaned_user = deduper.clean_content(user_msg or "")
        cleaned_assistant = deduper.clean_content(assistant_msg or "")
        if not cleaned_user and not cleaned_assistant:
            continue
        pair_hash = f"{hash(cleaned_user)}::{hash(cleaned_assistant)}"
        if pair_hash == prev_hash:
            continue
        cleaned_pairs.append((cleaned_user, cleaned_assistant))
        prev_hash = pair_hash
    if last_n > 0 and len(cleaned_pairs) > last_n:
        cleaned_pairs = cleaned_pairs[-last_n:]

    cleaned_pairs = formatter.truncate_to_limit(cleaned_pairs, max_tokens)
    total_text = "".join(user + assistant for user, assistant in cleaned_pairs)
    token_estimate = formatter.estimate_tokens(total_text)

    metadata = {"provider": provider}
    if session_path:
        metadata["session_path"] = str(session_path)

    return TransferContext(
        conversations=cleaned_pairs,
        source_session_id=session_id,
        token_estimate=token_estimate,
        metadata=metadata,
        stats=stats,
        source_provider=provider,
    )


def clean_entries(deduper, entries: list[ConversationEntry]) -> list[ConversationEntry]:
    result = []
    for entry in entries:
        cleaned = deduper.clean_content(entry.content)
        if cleaned or entry.tool_calls:
            result.append(
                ConversationEntry(
                    role=entry.role,
                    content=cleaned,
                    uuid=entry.uuid,
                    parent_uuid=entry.parent_uuid,
                    timestamp=entry.timestamp,
                    tool_calls=entry.tool_calls,
                )
            )
    return result


def build_pairs(entries: list[ConversationEntry]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    current_user: Optional[str] = None

    for entry in entries:
        if entry.role == "user":
            current_user = entry.content
        elif entry.role == "assistant" and current_user:
            pairs.append((current_user, entry.content))
            current_user = None

    return pairs


def extract_from_claude(
    *,
    work_dir: Path,
    parser,
    deduper,
    formatter,
    max_tokens: int,
    session_path: Optional[Path],
    last_n: int,
    include_stats: bool,
) -> TransferContext:
    resolved = parser.resolve_session(work_dir, session_path)
    info = parser.get_session_info(resolved)
    info.provider = "claude"

    stats = None
    if include_stats:
        stats = parser.extract_session_stats(resolved)

    entries = parser.parse_session(resolved)
    entries = clean_entries(deduper, entries)
    entries = deduper.dedupe_messages(entries)
    entries = deduper.collapse_tool_calls(entries)

    pairs = build_pairs(entries)
    if last_n > 0 and len(pairs) > last_n:
        pairs = pairs[-last_n:]

    pairs = formatter.truncate_to_limit(pairs, max_tokens)
    total_text = "".join(user + assistant for user, assistant in pairs)
    token_estimate = formatter.estimate_tokens(total_text)

    return TransferContext(
        conversations=pairs,
        source_session_id=info.session_id,
        token_estimate=token_estimate,
        metadata={"session_path": str(resolved), "provider": "claude"},
        stats=stats,
        source_provider="claude",
    )


def ensure_supported_provider(provider: str, supported_sources: tuple[str, ...]) -> None:
    if provider not in supported_sources:
        raise SessionNotFoundError(f"Unsupported source provider: {provider}")
