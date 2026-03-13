"""
Context transfer orchestration.

Coordinates the full pipeline: parse -> dedupe -> truncate -> format -> send.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from session_utils import find_project_session_file, legacy_project_config_dir, project_config_dir, resolve_project_config_dir
from .types import ConversationEntry, TransferContext, SessionNotFoundError, SessionStats
from .session_parser import ClaudeSessionParser
from .deduper import ConversationDeduper
from .formatter import ContextFormatter


class ContextTransfer:
    """Orchestrate context transfer between providers."""

    SUPPORTED_PROVIDERS = ("codex", "gemini", "opencode", "droid", "copilot", "codebuddy", "qwen")
    SUPPORTED_SOURCES = ("auto", "claude", "codex", "gemini", "opencode", "droid", "copilot", "codebuddy", "qwen")
    SOURCE_SESSION_FILES = {
        "claude": ".claude-session",
        "codex": ".codex-session",
        "gemini": ".gemini-session",
        "opencode": ".opencode-session",
        "droid": ".droid-session",
        "copilot": ".copilot-session",
        "codebuddy": ".codebuddy-session",
        "qwen": ".qwen-session",
    }
    DEFAULT_SOURCE_ORDER = ("claude", "codex", "gemini", "opencode", "droid", "copilot", "codebuddy", "qwen")
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

    def _load_session_data(self, provider: str) -> tuple[Optional[Path], dict]:
        filename = self.SOURCE_SESSION_FILES.get(provider)
        if not filename:
            return None, {}
        session_file = find_project_session_file(self.work_dir, filename)
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

    def _auto_source_candidates(self) -> list[str]:
        candidates: list[tuple[float, str]] = []
        for provider in self.DEFAULT_SOURCE_ORDER:
            filename = self.SOURCE_SESSION_FILES.get(provider)
            if not filename:
                continue
            session_file = find_project_session_file(self.work_dir, filename)
            if not session_file or not session_file.exists():
                continue
            try:
                mtime = session_file.stat().st_mtime
            except OSError:
                mtime = 0.0
            candidates.append((mtime, provider))
        ordered = [p for _, p in sorted(candidates, key=lambda x: x[0], reverse=True)]
        for provider in self.DEFAULT_SOURCE_ORDER:
            if provider not in ordered:
                ordered.append(provider)
        return ordered

    def _default_fetch_n(self) -> int:
        return self.DEFAULT_FALLBACK_PAIRS

    def _context_from_pairs(
        self,
        pairs: list[tuple[str, str]],
        *,
        provider: str,
        session_id: str,
        session_path: Optional[Path] = None,
        last_n: int = 3,
        stats: Optional[SessionStats] = None,
    ) -> TransferContext:
        cleaned_pairs: list[tuple[str, str]] = []
        prev_hash: Optional[str] = None
        for user_msg, assistant_msg in pairs:
            cleaned_user = self.deduper.clean_content(user_msg or "")
            cleaned_assistant = self.deduper.clean_content(assistant_msg or "")
            if not cleaned_user and not cleaned_assistant:
                continue
            pair_hash = f"{hash(cleaned_user)}::{hash(cleaned_assistant)}"
            if pair_hash == prev_hash:
                continue
            cleaned_pairs.append((cleaned_user, cleaned_assistant))
            prev_hash = pair_hash
        if last_n > 0 and len(cleaned_pairs) > last_n:
            cleaned_pairs = cleaned_pairs[-last_n:]

        cleaned_pairs = self.formatter.truncate_to_limit(cleaned_pairs, self.max_tokens)

        total_text = "".join(u + a for u, a in cleaned_pairs)
        token_estimate = self.formatter.estimate_tokens(total_text)

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

    def _clean_entries(
        self, entries: list[ConversationEntry]
    ) -> list[ConversationEntry]:
        """Clean all entries."""
        result = []
        for entry in entries:
            cleaned = self.deduper.clean_content(entry.content)
            if cleaned or entry.tool_calls:
                result.append(ConversationEntry(
                    role=entry.role,
                    content=cleaned,
                    uuid=entry.uuid,
                    parent_uuid=entry.parent_uuid,
                    timestamp=entry.timestamp,
                    tool_calls=entry.tool_calls,
                ))
        return result

    def _build_pairs(
        self, entries: list[ConversationEntry]
    ) -> list[tuple[str, str]]:
        """Build user/assistant conversation pairs."""
        pairs: list[tuple[str, str]] = []
        current_user: Optional[str] = None

        for entry in entries:
            if entry.role == "user":
                current_user = entry.content
            elif entry.role == "assistant" and current_user:
                pairs.append((current_user, entry.content))
                current_user = None

        return pairs

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
            return self._extract_from_claude(
                session_path=session_path,
                last_n=last_n,
                include_stats=include_stats,
            )
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
        resolved = self.parser.resolve_session(self.work_dir, session_path)
        info = self.parser.get_session_info(resolved)
        info.provider = "claude"

        stats = None
        if include_stats:
            stats = self.parser.extract_session_stats(resolved)

        entries = self.parser.parse_session(resolved)
        entries = self._clean_entries(entries)
        entries = self.deduper.dedupe_messages(entries)
        entries = self.deduper.collapse_tool_calls(entries)

        pairs = self._build_pairs(entries)
        if last_n > 0 and len(pairs) > last_n:
            pairs = pairs[-last_n:]

        pairs = self.formatter.truncate_to_limit(pairs, self.max_tokens)

        total_text = "".join(u + a for u, a in pairs)
        token_estimate = self.formatter.estimate_tokens(total_text)

        return TransferContext(
            conversations=pairs,
            source_session_id=info.session_id,
            token_estimate=token_estimate,
            metadata={"session_path": str(resolved), "provider": "claude"},
            stats=stats,
            source_provider="claude",
        )

    def _extract_from_codex(
        self,
        *,
        last_n: int,
        session_path: Optional[Path] = None,
        session_id: Optional[str] = None,
    ) -> TransferContext:
        session_file, data = self._load_session_data("codex")
        # Only use current active session, not old_* fallback to prevent "amnesia"
        log_path = session_path or (
            data.get("codex_session_path")
            or data.get("session_path")
        )
        session_id = session_id or (
            data.get("codex_session_id")
            or data.get("session_id")
            or ""
        )
        log_path_obj: Optional[Path] = None
        if log_path:
            try:
                log_path_obj = Path(str(log_path)).expanduser()
            except Exception:
                log_path_obj = None

        from codex_comm import CodexLogReader

        log_reader = CodexLogReader(
            log_path=log_path_obj if log_path_obj and log_path_obj.exists() else None,
            session_id_filter=session_id or None,
            work_dir=self.work_dir,
        )
        scan_path = log_reader._latest_log()
        if not scan_path or not scan_path.exists():
            raise SessionNotFoundError("No Codex session log found")

        fetch_n = last_n if last_n > 0 else self._default_fetch_n()
        pairs = log_reader.latest_conversations(fetch_n)

        session_path = log_path_obj if log_path_obj and log_path_obj.exists() else scan_path
        if not session_id and session_path:
            session_id = session_path.stem
        if not session_id:
            session_id = "unknown"

        return self._context_from_pairs(
            pairs,
            provider="codex",
            session_id=session_id,
            session_path=session_path,
            last_n=last_n,
        )

    def _extract_from_gemini(
        self,
        *,
        last_n: int,
        session_path: Optional[Path] = None,
        session_id: Optional[str] = None,
    ) -> TransferContext:
        session_file, data = self._load_session_data("gemini")
        # Only use current active session, not old_* fallback to prevent "amnesia"
        session_id = session_id or (
            data.get("gemini_session_id")
            or data.get("session_id")
            or ""
        )
        preferred_path = session_path or data.get("gemini_session_path")
        preferred_path_obj: Optional[Path] = None
        if preferred_path:
            try:
                preferred_path_obj = Path(str(preferred_path)).expanduser()
            except Exception:
                preferred_path_obj = None

        from gemini_comm import GeminiLogReader

        log_reader = GeminiLogReader(work_dir=self.work_dir)
        if preferred_path_obj and preferred_path_obj.exists():
            log_reader.set_preferred_session(preferred_path_obj)

        session_path = log_reader._latest_session()
        if not session_path or not session_path.exists():
            raise SessionNotFoundError("No Gemini session found")

        fetch_n = last_n if last_n > 0 else self._default_fetch_n()
        pairs = log_reader.latest_conversations(fetch_n)

        if not session_id and session_path:
            session_id = session_path.stem
        if not session_id:
            session_id = "unknown"

        return self._context_from_pairs(
            pairs,
            provider="gemini",
            session_id=session_id,
            session_path=session_path,
            last_n=last_n,
        )

    def _extract_from_droid(
        self,
        *,
        last_n: int,
        session_path: Optional[Path] = None,
        session_id: Optional[str] = None,
    ) -> TransferContext:
        session_file, data = self._load_session_data("droid")
        # Only use current active session, not old_* fallback to prevent "amnesia"
        session_id = session_id or (
            data.get("droid_session_id")
            or data.get("session_id")
            or ""
        )
        preferred_path = session_path or data.get("droid_session_path")
        preferred_path_obj: Optional[Path] = None
        if preferred_path:
            try:
                preferred_path_obj = Path(str(preferred_path)).expanduser()
            except Exception:
                preferred_path_obj = None

        from droid_comm import DroidLogReader

        log_reader = DroidLogReader(work_dir=self.work_dir)
        if preferred_path_obj and preferred_path_obj.exists():
            log_reader.set_preferred_session(preferred_path_obj)
        if session_id:
            log_reader.set_session_id_hint(session_id)

        session_path = log_reader.current_session_path()
        if not session_path or not session_path.exists():
            raise SessionNotFoundError("No Droid session found")

        fetch_n = last_n if last_n > 0 else self._default_fetch_n()
        pairs = log_reader.latest_conversations(fetch_n)

        if not session_id and session_path:
            session_id = session_path.stem
        if not session_id:
            session_id = "unknown"

        return self._context_from_pairs(
            pairs,
            provider="droid",
            session_id=session_id,
            session_path=session_path,
            last_n=last_n,
        )

    def _extract_from_opencode(
        self,
        *,
        last_n: int,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> TransferContext:
        session_file, data = self._load_session_data("opencode")
        # Only use current active session, not old_* fallback to prevent "amnesia"
        session_id = session_id or (
            data.get("opencode_session_id")
            or data.get("opencode_storage_session_id")
            or data.get("session_id")
            or ""
        )
        project_id = project_id or data.get("opencode_project_id") or ""

        from opencode_comm import OpenCodeLogReader

        log_reader = OpenCodeLogReader(
            work_dir=self.work_dir,
            project_id=project_id or "global",
            session_id_filter=session_id or None,
        )
        session_path = None
        if not session_id:
            state = log_reader.capture_state()
            session_path = state.get("session_path")
            session_id = state.get("session_id") or ""
            if not session_id and session_path:
                try:
                    session_id = Path(session_path).stem
                except Exception:
                    session_id = ""
            if not session_id:
                raise SessionNotFoundError("No OpenCode session found")

        fetch_n = last_n if last_n > 0 else self._default_fetch_n()
        if hasattr(log_reader, "conversations_for_session") and session_id:
            pairs = log_reader.conversations_for_session(session_id, fetch_n)
        else:
            pairs = log_reader.latest_conversations(fetch_n)

        session_path_obj: Optional[Path] = None
        if session_path:
            try:
                session_path_obj = session_path if isinstance(session_path, Path) else Path(str(session_path)).expanduser()
            except Exception:
                session_path_obj = None

        return self._context_from_pairs(
            pairs,
            provider="opencode",
            session_id=session_id or "unknown",
            session_path=session_path_obj,
            last_n=last_n,
        )

    def format_output(
        self,
        context: TransferContext,
        fmt: str = "markdown",
        detailed: bool = False,
    ) -> str:
        """Format context for output."""
        return self.formatter.format(context, fmt, detailed=detailed)

    def send_to_provider(
        self,
        context: TransferContext,
        provider: str,
        fmt: str = "markdown",
    ) -> tuple[bool, str]:
        """Send context to a provider via ask command."""
        if provider not in self.SUPPORTED_PROVIDERS:
            return False, f"Unsupported provider: {provider}"

        formatted = self.format_output(context, fmt)

        # Build the ask command
        cmd_map = {
            "codex": "cask",
            "gemini": "gask",
            "opencode": "oask",
            "droid": "dask",
        }
        cmd = cmd_map.get(provider, "ask")

        try:
            result = subprocess.run(
                [cmd, "--sync", formatted],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return True, result.stdout
            return False, result.stderr or f"Command failed with code {result.returncode}"
        except FileNotFoundError:
            return False, f"Command not found: {cmd}"
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def save_transfer(
        self,
        context: TransferContext,
        fmt: str = "markdown",
        target_provider: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Path:
        """Save transfer to ./.ccb/history/ with timestamp."""
        history_dir = self._history_dir()
        history_dir.mkdir(parents=True, exist_ok=True)

        ext = {"markdown": "md", "plain": "txt", "json": "json"}.get(fmt, "md")
        if filename:
            safe = str(filename).strip().replace("/", "-").replace("\\", "-")
            if not Path(safe).suffix:
                safe = f"{safe}.{ext}"
            filepath = history_dir / safe
        else:
            # Generate filename: {source}-YYYYMMDD-HHMMSS-{session_id}[-to-{provider}].md
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            session_short = context.source_session_id[:8]
            source_provider = (context.source_provider or context.metadata.get("provider") or "session").strip().lower()
            if not source_provider:
                source_provider = "session"
            source_provider = source_provider.replace("/", "-").replace("\\", "-")
            provider_suffix = f"-to-{target_provider}" if target_provider else ""
            filepath = history_dir / f"{source_provider}-{ts}-{session_short}{provider_suffix}.{ext}"

        formatted = self.format_output(context, fmt)
        filepath.write_text(formatted, encoding="utf-8")

        return filepath

    def _history_dir(self) -> Path:
        """Resolve local history directory under the project config dir."""
        try:
            work_dir = Path(self.work_dir).expanduser()
        except Exception:
            work_dir = Path.cwd()

        primary = project_config_dir(work_dir)
        legacy = legacy_project_config_dir(work_dir)

        if not primary.exists() and legacy.is_dir():
            try:
                legacy.replace(primary)
            except Exception:
                base = legacy
            else:
                base = primary
        else:
            base = resolve_project_config_dir(work_dir)

        base.mkdir(parents=True, exist_ok=True)
        return base / "history"
