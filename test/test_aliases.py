"""Tests for lib/aliases.py — agent name alias resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aliases import DEFAULT_ALIASES, _load_json, load_aliases, resolve_alias


# ---------------------------------------------------------------------------
# resolve_alias
# ---------------------------------------------------------------------------

class TestResolveAlias:
    def test_known_alias(self):
        aliases = {"a": "codex", "b": "gemini"}
        assert resolve_alias("a", aliases) == "codex"

    def test_unknown_passthrough(self):
        assert resolve_alias("kimi", {}) == "kimi"

    def test_case_insensitive(self):
        aliases = {"a": "codex"}
        assert resolve_alias("A", aliases) == "codex"

    def test_whitespace_stripped(self):
        aliases = {"a": "codex"}
        assert resolve_alias("  a  ", aliases) == "codex"

    def test_empty_string(self):
        assert resolve_alias("", {"": "x"}) == "x"
        assert resolve_alias("", {}) == ""

    def test_none_safe(self):
        assert resolve_alias(None, {}) == ""


# ---------------------------------------------------------------------------
# _load_json
# ---------------------------------------------------------------------------

class TestLoadJson:
    def test_missing_file(self, tmp_path: Path):
        assert _load_json(tmp_path / "nope.json") == {}

    def test_valid_file(self, tmp_path: Path):
        f = tmp_path / "a.json"
        f.write_text(json.dumps({"x": "codex", "y": "gemini"}))
        assert _load_json(f) == {"x": "codex", "y": "gemini"}

    def test_corrupt_json(self, tmp_path: Path):
        f = tmp_path / "bad.json"
        f.write_text("{not valid json")
        assert _load_json(f) == {}

    def test_non_dict_json(self, tmp_path: Path):
        f = tmp_path / "arr.json"
        f.write_text(json.dumps([1, 2, 3]))
        assert _load_json(f) == {}

    def test_coerces_values_to_str(self, tmp_path: Path):
        f = tmp_path / "mixed.json"
        f.write_text(json.dumps({"a": 123, "b": True}))
        result = _load_json(f)
        assert result == {"a": "123", "b": "True"}


# ---------------------------------------------------------------------------
# load_aliases
# ---------------------------------------------------------------------------

class TestLoadAliases:
    def test_defaults_only(self, tmp_path: Path):
        """No config files → returns DEFAULT_ALIASES."""
        result = load_aliases(work_dir=tmp_path)
        assert result == DEFAULT_ALIASES

    def test_global_overrides_default(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        ccb_dir = home / ".ccb"
        ccb_dir.mkdir(parents=True)
        (ccb_dir / "aliases.json").write_text(json.dumps({"a": "gemini"}))

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        result = load_aliases(work_dir=tmp_path / "project")
        assert result["a"] == "gemini"
        # Other defaults still present
        assert result["b"] == DEFAULT_ALIASES["b"]

    def test_project_overrides_global(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        ccb_dir = home / ".ccb"
        ccb_dir.mkdir(parents=True)
        (ccb_dir / "aliases.json").write_text(json.dumps({"a": "gemini"}))

        proj = tmp_path / "project"
        proj_ccb = proj / ".ccb"
        proj_ccb.mkdir(parents=True)
        (proj_ccb / "aliases.json").write_text(json.dumps({"a": "kimi"}))

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        result = load_aliases(work_dir=proj)
        assert result["a"] == "kimi"

    def test_no_work_dir(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        result = load_aliases(work_dir=None)
        assert result == DEFAULT_ALIASES

    def test_custom_alias_added(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        ccb_dir = home / ".ccb"
        ccb_dir.mkdir(parents=True)
        (ccb_dir / "aliases.json").write_text(json.dumps({"z": "deepseek"}))

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        result = load_aliases(work_dir=tmp_path)
        assert result["z"] == "deepseek"
        # Defaults preserved
        assert result["a"] == DEFAULT_ALIASES["a"]


# ---------------------------------------------------------------------------
# Alias + instance (colon-separated) integration
# ---------------------------------------------------------------------------

class TestAliasWithInstance:
    """Test the pattern used in bin/ask: alias:instance resolution."""

    def test_alias_with_instance(self):
        aliases = DEFAULT_ALIASES
        raw = "a:review"
        base, _, instance = raw.partition(":")
        resolved = resolve_alias(base, aliases)
        result = f"{resolved}:{instance}" if instance else resolved
        assert result == "codex:review"

    def test_plain_alias(self):
        aliases = DEFAULT_ALIASES
        raw = "b"
        base, _, instance = raw.partition(":")
        resolved = resolve_alias(base, aliases)
        result = f"{resolved}:{instance}" if instance else resolved
        assert result == "gemini"

    def test_non_alias_with_instance(self):
        aliases = DEFAULT_ALIASES
        raw = "codex:auth"
        base, _, instance = raw.partition(":")
        resolved = resolve_alias(base, aliases)
        result = f"{resolved}:{instance}" if instance else resolved
        assert result == "codex:auth"

    def test_non_alias_plain(self):
        aliases = DEFAULT_ALIASES
        raw = "kimi"
        base, _, instance = raw.partition(":")
        resolved = resolve_alias(base, aliases)
        result = f"{resolved}:{instance}" if instance else resolved
        assert result == "kimi"


# ---------------------------------------------------------------------------
# Integration with parse_qualified_provider
# ---------------------------------------------------------------------------

class TestIntegrationWithProviders:
    """Verify alias resolution works with parse_qualified_provider."""

    def test_alias_then_parse(self):
        from providers import parse_qualified_provider

        aliases = DEFAULT_ALIASES
        raw = "a:review"
        base, _, instance = raw.partition(":")
        base = resolve_alias(base, aliases)
        qualified = f"{base}:{instance}" if instance else base

        provider, inst = parse_qualified_provider(qualified)
        assert provider == "codex"
        assert inst == "review"

    def test_plain_alias_then_parse(self):
        from providers import parse_qualified_provider

        aliases = DEFAULT_ALIASES
        raw = "c"
        base, _, instance = raw.partition(":")
        base = resolve_alias(base, aliases)
        qualified = f"{base}:{instance}" if instance else base

        provider, inst = parse_qualified_provider(qualified)
        assert provider == "claude"
        assert inst is None
