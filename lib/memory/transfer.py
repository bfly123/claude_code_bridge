"""
Context transfer orchestration.

Coordinates the full pipeline: parse -> dedupe -> truncate -> format -> send.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .types import TransferContext, SessionNotFoundError
from .session_parser import ClaudeSessionParser
from .deduper import ConversationDeduper
from .formatter import ContextFormatter
from .transfer_runtime import (
    auto_source_candidates,
    extract_from_claude,
    extract_from_codex,
    extract_from_droid,
    extract_from_gemini,
    extract_from_opencode,
    history_dir,
    save_transfer as save_transfer_output,
    send_to_agent as send_transfer_to_agent,
)


class ContextTransfer:
    """Orchestrate context transfer between providers."""

    SUPPORTED_SOURCES = ("auto", "claude", "codex", "gemini", "opencode", "droid")
    SOURCE_SESSION_FILES = {
        "claude": ".claude-session",
        "codex": ".codex-session",
        "gemini": ".gemini-session",
        "opencode": ".opencode-session",
        "droid": ".droid-session",
    }
    DEFAULT_SOURCE_ORDER = ("claude", "codex", "gemini", "opencode", "droid")
    DEFAULT_FALLBACK_PAIRS = 50

    def __init__(
        self,
        max_tokens: int = 8000,
        work_dir: Optional[Path] = None,
    ):
        self.max_tokens = max_tokens
        self.work_dir = work_dir or Path.cwd()
        self.parser = ClaudeSessionParser()
        self.deduper = ConversationDeduper()
        self.formatter = ContextFormatter(max_tokens=max_tokens)

    def _normalize_provider(self, provider: Optional[str]) -> str:
        value = (provider or "auto").strip().lower()
        return value or "auto"

    def _auto_source_candidates(self) -> list[str]:
        return auto_source_candidates(self.work_dir, self.DEFAULT_SOURCE_ORDER, self.SOURCE_SESSION_FILES)

    def extract_conversations(
        self,
        session_path: Optional[Path] = None,
        last_n: int = 3,
        include_stats: bool = True,
        source_provider: str = "auto",
        source_session_id: Optional[str] = None,
        source_project_id: Optional[str] = None,
    ) -> TransferContext:
        """Extract and process conversations from a session."""
        provider = self._normalize_provider(source_provider)
        if provider == "auto":
            if session_path:
                return self._extract_from_claude(
                    session_path=session_path,
                    last_n=last_n,
                    include_stats=include_stats,
                )
            last_error: Optional[Exception] = None
            for candidate in self._auto_source_candidates():
                try:
                    return self._extract_by_provider(
                        candidate,
                        session_path=session_path,
                        last_n=last_n,
                        include_stats=include_stats,
                        source_session_id=source_session_id,
                        source_project_id=source_project_id,
                    )
                except SessionNotFoundError as exc:
                    last_error = exc
                    continue
            if last_error:
                raise last_error
            raise SessionNotFoundError("No sessions found for any provider")

        return self._extract_by_provider(
            provider,
            session_path=session_path,
            last_n=last_n,
            include_stats=include_stats,
            source_session_id=source_session_id,
            source_project_id=source_project_id,
        )

    def _extract_by_provider(
        self,
        provider: str,
        *,
        session_path: Optional[Path],
        last_n: int,
        include_stats: bool,
        source_session_id: Optional[str],
        source_project_id: Optional[str],
    ) -> TransferContext:
        if provider == "claude":
            return self._extract_from_claude(session_path=session_path, last_n=last_n, include_stats=include_stats)
        if provider == "codex":
            return self._extract_from_codex(
                last_n=last_n,
                session_path=session_path,
                session_id=source_session_id,
            )
        if provider == "gemini":
            return self._extract_from_gemini(
                last_n=last_n,
                session_path=session_path,
                session_id=source_session_id,
            )
        if provider == "opencode":
            return self._extract_from_opencode(
                last_n=last_n,
                session_id=source_session_id,
                project_id=source_project_id,
            )
        if provider == "droid":
            return self._extract_from_droid(
                last_n=last_n,
                session_path=session_path,
                session_id=source_session_id,
            )
        raise SessionNotFoundError(f"Unsupported source provider: {provider}")

    def _extract_from_claude(
        self,
        *,
        session_path: Optional[Path],
        last_n: int,
        include_stats: bool,
    ) -> TransferContext:
        return extract_from_claude(
            work_dir=self.work_dir,
            parser=self.parser,
            deduper=self.deduper,
            formatter=self.formatter,
            max_tokens=self.max_tokens,
            session_path=session_path,
            last_n=last_n,
            include_stats=include_stats,
        )

    def _extract_from_codex(
        self,
        *,
        last_n: int,
        session_path: Optional[Path] = None,
        session_id: Optional[str] = None,
    ) -> TransferContext:
        return extract_from_codex(
            work_dir=self.work_dir,
            source_session_files=self.SOURCE_SESSION_FILES,
            deduper=self.deduper,
            formatter=self.formatter,
            max_tokens=self.max_tokens,
            fallback_pairs=self.DEFAULT_FALLBACK_PAIRS,
            last_n=last_n,
            session_path=session_path,
            session_id=session_id,
        )

    def _extract_from_gemini(
        self,
        *,
        last_n: int,
        session_path: Optional[Path] = None,
        session_id: Optional[str] = None,
    ) -> TransferContext:
        return extract_from_gemini(
            work_dir=self.work_dir,
            source_session_files=self.SOURCE_SESSION_FILES,
            deduper=self.deduper,
            formatter=self.formatter,
            max_tokens=self.max_tokens,
            fallback_pairs=self.DEFAULT_FALLBACK_PAIRS,
            last_n=last_n,
            session_path=session_path,
            session_id=session_id,
        )

    def _extract_from_droid(
        self,
        *,
        last_n: int,
        session_path: Optional[Path] = None,
        session_id: Optional[str] = None,
    ) -> TransferContext:
        return extract_from_droid(
            work_dir=self.work_dir,
            source_session_files=self.SOURCE_SESSION_FILES,
            deduper=self.deduper,
            formatter=self.formatter,
            max_tokens=self.max_tokens,
            fallback_pairs=self.DEFAULT_FALLBACK_PAIRS,
            last_n=last_n,
            session_path=session_path,
            session_id=session_id,
        )

    def _extract_from_opencode(
        self,
        *,
        last_n: int,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> TransferContext:
        return extract_from_opencode(
            work_dir=self.work_dir,
            source_session_files=self.SOURCE_SESSION_FILES,
            deduper=self.deduper,
            formatter=self.formatter,
            max_tokens=self.max_tokens,
            fallback_pairs=self.DEFAULT_FALLBACK_PAIRS,
            last_n=last_n,
            session_id=session_id,
            project_id=project_id,
        )

    def format_output(
        self,
        context: TransferContext,
        fmt: str = "markdown",
        detailed: bool = False,
    ) -> str:
        """Format context for output."""
        return self.formatter.format(context, fmt, detailed=detailed)

    def send_to_agent(
        self,
        context: TransferContext,
        agent_name: str,
        fmt: str = "markdown",
    ) -> tuple[bool, str]:
        """Send context to an agent via ask command."""
        formatted = self.format_output(context, fmt)
        return send_transfer_to_agent(
            agent_name=agent_name,
            formatted=formatted,
            work_dir=self.work_dir,
        )

    def save_transfer(
        self,
        context: TransferContext,
        fmt: str = "markdown",
        target_agent: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Path:
        return save_transfer_output(
            work_dir=self.work_dir,
            format_output_fn=self.format_output,
            context=context,
            fmt=fmt,
            target_agent=target_agent,
            filename=filename,
        )

    def _history_dir(self) -> Path:
        return history_dir(self.work_dir)
