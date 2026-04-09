from __future__ import annotations

from pathlib import Path
from typing import Optional

from .types import SessionNotFoundError, TransferContext
from .transfer_runtime import (
    auto_source_candidates,
    extract_from_claude,
    extract_from_codex,
    extract_from_droid,
    extract_from_gemini,
    extract_from_opencode,
)


class ContextTransferSourceMixin:
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

    def _normalize_provider(self, provider: Optional[str]) -> str:
        value = (provider or "auto").strip().lower()
        return value or "auto"

    def _auto_source_candidates(self) -> list[str]:
        return auto_source_candidates(self.work_dir, self.DEFAULT_SOURCE_ORDER, self.SOURCE_SESSION_FILES)

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


__all__ = ["ContextTransferSourceMixin"]
