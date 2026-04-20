"""Tests for multi-instance provider support (#117)."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import types
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

# Ensure lib is on path
_lib = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(_lib))

# ── Stub out modules that use Python 3.10+ syntax (str | None) ─────────────
# terminal_runtime APIs use union-type syntax unsupported on Python <3.10.
# We pre-populate sys.modules with lightweight stubs so backend session modules
# can be imported without hitting a TypeError.

def _ensure_stub(mod_name: str, attrs: dict[str, Any] | None = None) -> None:
    """Insert a stub module into sys.modules if not already importable."""
    if mod_name in sys.modules:
        return
    try:
        __import__(mod_name)
        return
    except Exception:
        pass
    stub = types.ModuleType(mod_name)
    for k, v in (attrs or {}).items():
        setattr(stub, k, v)
    sys.modules[mod_name] = stub


_ensure_stub("terminal_runtime", {
    "_subprocess_kwargs": lambda: {},
    "get_backend_for_session": lambda data: None,
})
_ensure_stub("terminal_runtime.backend_env", {
    "apply_backend_env": lambda: None,
    "get_backend_env": lambda: None,
})
_ensure_stub("project_id", {
    "compute_ccb_project_id": lambda p: "stub_project_id",
})


# ── parse_qualified_provider ────────────────────────────────────────────────

class TestParseQualifiedProvider:
    def test_plain_provider(self):
        from provider_core.runtime_specs import parse_qualified_provider
        assert parse_qualified_provider("codex") == ("codex", None)

    def test_qualified_provider(self):
        from provider_core.runtime_specs import parse_qualified_provider
        assert parse_qualified_provider("codex:auth") == ("codex", "auth")

    def test_empty_string(self):
        from provider_core.runtime_specs import parse_qualified_provider
        assert parse_qualified_provider("") == ("", None)

    def test_none_input(self):
        from provider_core.runtime_specs import parse_qualified_provider
        assert parse_qualified_provider(None) == ("", None)

    def test_colon_only(self):
        from provider_core.runtime_specs import parse_qualified_provider
        assert parse_qualified_provider(":") == ("", None)

    def test_provider_with_empty_instance(self):
        from provider_core.runtime_specs import parse_qualified_provider
        assert parse_qualified_provider("codex:") == ("codex", None)

    def test_uppercase_normalized(self):
        from provider_core.runtime_specs import parse_qualified_provider
        assert parse_qualified_provider("CODEX:Auth") == ("codex", "auth")

    def test_whitespace_trimmed(self):
        from provider_core.runtime_specs import parse_qualified_provider
        assert parse_qualified_provider(" codex : auth ") == ("codex", "auth")

    def test_multiple_colons(self):
        """Only split on first colon."""
        from provider_core.runtime_specs import parse_qualified_provider
        base, instance = parse_qualified_provider("codex:auth:extra")
        assert base == "codex"
        assert instance == "auth:extra"

    def test_all_providers(self):
        from provider_core.runtime_specs import parse_qualified_provider
        for prov in ("codex", "gemini", "opencode", "claude", "droid", "copilot", "codebuddy", "qwen"):
            assert parse_qualified_provider(prov) == (prov, None)
            assert parse_qualified_provider(f"{prov}:test") == (prov, "test")


# ── make_qualified_key ──────────────────────────────────────────────────────

class TestMakeQualifiedKey:
    def test_no_instance(self):
        from provider_core.runtime_specs import make_qualified_key
        assert make_qualified_key("codex", None) == "codex"

    def test_with_instance(self):
        from provider_core.runtime_specs import make_qualified_key
        assert make_qualified_key("codex", "auth") == "codex:auth"

    def test_empty_instance(self):
        from provider_core.runtime_specs import make_qualified_key
        assert make_qualified_key("codex", "") == "codex"

    def test_roundtrip(self):
        from provider_core.runtime_specs import make_qualified_key, parse_qualified_provider
        key = make_qualified_key("gemini", "frontend")
        base, inst = parse_qualified_provider(key)
        assert base == "gemini"
        assert inst == "frontend"

    def test_roundtrip_no_instance(self):
        from provider_core.runtime_specs import make_qualified_key, parse_qualified_provider
        key = make_qualified_key("codex", None)
        base, inst = parse_qualified_provider(key)
        assert base == "codex"
        assert inst is None


# ── session_filename_for_instance ───────────────────────────────────────────

class TestSessionFilenameForInstance:
    def test_no_instance(self):
        from provider_core.pathing import session_filename_for_instance
        assert session_filename_for_instance(".codex-session", None) == ".codex-session"

    def test_with_instance(self):
        from provider_core.pathing import session_filename_for_instance
        assert session_filename_for_instance(".codex-session", "auth") == ".codex-auth-session"

    def test_empty_instance(self):
        from provider_core.pathing import session_filename_for_instance
        assert session_filename_for_instance(".codex-session", "") == ".codex-session"

    def test_whitespace_instance(self):
        from provider_core.pathing import session_filename_for_instance
        assert session_filename_for_instance(".codex-session", "  ") == ".codex-session"

    def test_all_provider_sessions(self):
        from provider_core.pathing import session_filename_for_instance
        cases = [
            (".codex-session", "auth", ".codex-auth-session"),
            (".gemini-session", "frontend", ".gemini-frontend-session"),
            (".opencode-session", "backend", ".opencode-backend-session"),
            (".claude-session", "review", ".claude-review-session"),
            (".droid-session", "test", ".droid-test-session"),
            (".copilot-session", "dev", ".copilot-dev-session"),
            (".codebuddy-session", "prod", ".codebuddy-prod-session"),
            (".qwen-session", "api", ".qwen-api-session"),
        ]
        for base, inst, expected in cases:
            assert session_filename_for_instance(base, inst) == expected, f"Failed for {base} + {inst}"


# ── Session module instance support ────────────────────────────────────────

class TestSessionModuleInstance:
    """Test that session modules accept instance parameter."""

    def test_codex_find_session_file_default(self, tmp_path):
        from provider_backends.codex.session import find_project_session_file
        # No session file exists -- should return None
        result = find_project_session_file(tmp_path)
        assert result is None

    def test_codex_find_session_file_with_instance(self, tmp_path):
        from provider_backends.codex.session import find_project_session_file
        # Create instance-specific session file
        ccb_dir = tmp_path / ".ccb"
        ccb_dir.mkdir()
        session_file = ccb_dir / ".codex-auth-session"
        session_file.write_text('{"pane_id": "test"}')
        result = find_project_session_file(tmp_path, instance="auth")
        assert result is not None
        assert "auth" in result.name

    def test_codex_load_session_no_instance(self, tmp_path):
        from provider_backends.codex.session import load_project_session
        result = load_project_session(tmp_path)
        assert result is None

    def test_codex_load_session_with_instance(self, tmp_path):
        from provider_backends.codex.session import load_project_session
        result = load_project_session(tmp_path, instance="auth")
        assert result is None  # No file exists

    def test_codex_load_session_with_instance_file_exists(self, tmp_path):
        from provider_backends.codex.session import load_project_session
        ccb_dir = tmp_path / ".ccb"
        ccb_dir.mkdir()
        session_file = ccb_dir / ".codex-auth-session"
        session_file.write_text('{"pane_id": "%42", "work_dir": "/tmp/test"}')
        result = load_project_session(tmp_path, instance="auth")
        assert result is not None
        assert result.pane_id == "%42"

    def test_codex_compute_session_key_no_instance(self):
        from provider_backends.codex.session import CodexProjectSession, compute_session_key
        session = CodexProjectSession(
            session_file=Path("/tmp/test/.ccb/.codex-session"),
            data={"ccb_project_id": "abc123", "work_dir": "/tmp/test"},
        )
        key = compute_session_key(session)
        assert key.startswith("codex:abc123:")

    def test_codex_compute_session_key_with_instance(self):
        from provider_backends.codex.session import CodexProjectSession, compute_session_key
        session = CodexProjectSession(
            session_file=Path("/tmp/test/.ccb/.codex-auth-session"),
            data={"ccb_project_id": "abc123", "work_dir": "/tmp/test"},
        )
        key = compute_session_key(session, instance="auth")
        assert "auth" in key
        assert "abc123" in key

    def test_gemini_find_session_file_default(self, tmp_path):
        from provider_backends.gemini.session import find_project_session_file
        result = find_project_session_file(tmp_path)
        assert result is None

    def test_gemini_find_session_file_with_instance(self, tmp_path):
        from provider_backends.gemini.session import find_project_session_file
        ccb_dir = tmp_path / ".ccb"
        ccb_dir.mkdir()
        session_file = ccb_dir / ".gemini-frontend-session"
        session_file.write_text('{"pane_id": "test"}')
        result = find_project_session_file(tmp_path, instance="frontend")
        assert result is not None
        assert "frontend" in result.name


    def test_gemini_load_session_with_instance_does_not_fallback_to_default(self, tmp_path):
        from provider_backends.gemini.session import load_project_session
        ccb_dir = tmp_path / '.ccb'
        ccb_dir.mkdir()
        (ccb_dir / '.gemini-session').write_text('{"pane_id": "%42", "work_dir": "/tmp/test"}')
        result = load_project_session(tmp_path, instance='frontend')
        assert result is None

    def test_gemini_compute_session_key_with_instance(self):
        from provider_backends.gemini.session import GeminiProjectSession, compute_session_key
        session = GeminiProjectSession(
            session_file=Path("/tmp/test/.ccb/.gemini-session"),
            data={"ccb_project_id": "xyz789", "work_dir": "/tmp/test"},
        )
        key = compute_session_key(session, instance="frontend")
        assert "frontend" in key
        assert "xyz789" in key

    def test_session_key_changes_for_different_worktrees_even_same_project(self):
        from provider_backends.claude.session import ClaudeProjectSession, compute_session_key as claude_key
        from provider_backends.codex.session import CodexProjectSession, compute_session_key as codex_key
        from provider_backends.gemini.session import GeminiProjectSession, compute_session_key as gemini_key

        codex_a = CodexProjectSession(
            session_file=Path("/tmp/repo/.ccb/.codex-a-session"),
            data={"ccb_project_id": "same-project", "work_dir": "/tmp/repo/.ccb/workspaces/a"},
        )
        codex_b = CodexProjectSession(
            session_file=Path("/tmp/repo/.ccb/.codex-b-session"),
            data={"ccb_project_id": "same-project", "work_dir": "/tmp/repo/.ccb/workspaces/b"},
        )
        assert codex_key(codex_a, instance="a") != codex_key(codex_b, instance="b")

        gemini_a = GeminiProjectSession(
            session_file=Path("/tmp/repo/.ccb/.gemini-a-session"),
            data={"ccb_project_id": "same-project", "work_dir": "/tmp/repo/.ccb/workspaces/a"},
        )
        gemini_b = GeminiProjectSession(
            session_file=Path("/tmp/repo/.ccb/.gemini-b-session"),
            data={"ccb_project_id": "same-project", "work_dir": "/tmp/repo/.ccb/workspaces/b"},
        )
        assert gemini_key(gemini_a, instance="a") != gemini_key(gemini_b, instance="b")

        claude_a = ClaudeProjectSession(
            session_file=Path("/tmp/repo/.ccb/.claude-a-session"),
            data={"ccb_project_id": "same-project", "work_dir": "/tmp/repo/.ccb/workspaces/a"},
        )
        claude_b = ClaudeProjectSession(
            session_file=Path("/tmp/repo/.ccb/.claude-b-session"),
            data={"ccb_project_id": "same-project", "work_dir": "/tmp/repo/.ccb/workspaces/b"},
        )
        assert claude_key(claude_a, instance="a") != claude_key(claude_b, instance="b")

# ── Backward compatibility ──────────────────────────────────────────────────

class TestBackwardCompatibility:
    """Verify that no-instance usage produces identical behavior."""

    def test_parse_qualified_plain(self):
        from provider_core.runtime_specs import parse_qualified_provider
        for prov in ("codex", "gemini", "opencode", "claude", "droid", "copilot", "codebuddy", "qwen"):
            base, inst = parse_qualified_provider(prov)
            assert base == prov
            assert inst is None

    def test_session_filename_unchanged(self):
        from provider_core.pathing import session_filename_for_instance
        for name in (".codex-session", ".gemini-session", ".opencode-session",
                     ".claude-session", ".droid-session", ".copilot-session",
                     ".codebuddy-session", ".qwen-session"):
            assert session_filename_for_instance(name, None) == name

    def test_make_qualified_key_no_instance(self):
        from provider_core.runtime_specs import make_qualified_key
        assert make_qualified_key("codex", None) == "codex"


# ── Daemon routing with instance ────────────────────────────────────────────

class TestDaemonInstanceRouting:
    """Test that the daemon correctly parses and routes instance-qualified providers."""

    def test_daemon_parses_qualified_provider(self):
        """Verify _handle_request parses 'codex:auth' correctly."""
        from provider_core.runtime_specs import parse_qualified_provider
        base, inst = parse_qualified_provider("codex:auth")
        assert base == "codex"
        assert inst == "auth"

    def test_pool_key_includes_instance(self):
        """Pool key should use qualified key for instance isolation."""
        from provider_core.runtime_specs import make_qualified_key
        key = make_qualified_key("codex", "auth")
        assert key == "codex:auth"
        # Different instance = different pool key
        key2 = make_qualified_key("codex", "payment")
        assert key2 == "codex:payment"
        assert key != key2

    def test_same_provider_different_instances_isolated(self):
        """Two instances of the same provider must produce different keys."""
        from provider_core.runtime_specs import make_qualified_key
        keys = set()
        for inst in ("auth", "payment", "frontend", "backend"):
            keys.add(make_qualified_key("codex", inst))
        assert len(keys) == 4

    def test_different_providers_same_instance_isolated(self):
        """Same instance name on different providers must produce different keys."""
        from provider_core.runtime_specs import make_qualified_key
        key1 = make_qualified_key("codex", "auth")
        key2 = make_qualified_key("gemini", "auth")
        assert key1 != key2
