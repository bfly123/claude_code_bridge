"""
Context transfer orchestration.

Coordinates the full pipeline: parse -> dedupe -> truncate -> format -> send.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .types import SessionNotFoundError, TransferContext
from .session_parser import ClaudeSessionParser
from .deduper import ConversationDeduper
from .formatter import ContextFormatter
from .transfer_sources import ContextTransferSourceMixin
from .transfer_runtime import (
    history_dir,
    save_transfer as save_transfer_output,
    send_to_agent as send_transfer_to_agent,
)


class ContextTransfer(ContextTransferSourceMixin):
    """Orchestrate context transfer between providers."""

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
