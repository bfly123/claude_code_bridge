"""Tests for lib/team_config.py — team configuration and agent resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from team_config import (
    VALID_STRATEGIES,
    TeamAgent,
    TeamConfig,
    _load_team_json,
    _parse_agent,
    load_team_config,
    resolve_team_agent,
)


# ---------------------------------------------------------------------------
# TeamAgent / TeamConfig dataclasses
# ---------------------------------------------------------------------------

class TestTeamConfig:
    def test_agent_map_lookup(self):
        team = TeamConfig(
            name="test",
            agents=[
                TeamAgent(name="coder", provider="codex", model="o3", role="implementation"),
                TeamAgent(name="reviewer", provider="claude", role="review"),
            ],
        )
        m = team.agent_map()
        assert m["coder"].provider == "codex"
        assert m["reviewer"].provider == "claude"

    def test_agent_map_case_insensitive(self):
        team = TeamConfig(
            name="test",
            agents=[TeamAgent(name="Coder", provider="codex")],
        )
        # Names are lowered during parse, but test direct construction
        m = team.agent_map()
        assert "coder" in m

    def test_empty_agents(self):
        team = TeamConfig(name="empty", agents=[])
        assert team.agent_map() == {}


# ---------------------------------------------------------------------------
# _parse_agent
# ---------------------------------------------------------------------------

class TestParseAgent:
    def test_valid_agent(self):
        raw = {"name": "coder", "provider": "codex", "model": "o3", "role": "implementation", "skills": ["python", "rust"]}
        agent = _parse_agent(raw)
        assert agent is not None
        assert agent.name == "coder"
        assert agent.provider == "codex"
        assert agent.model == "o3"
        assert agent.role == "implementation"
        assert agent.skills == ["python", "rust"]

    def test_minimal_agent(self):
        raw = {"name": "bot", "provider": "gemini"}
        agent = _parse_agent(raw)
        assert agent is not None
        assert agent.name == "bot"
        assert agent.provider == "gemini"
        assert agent.model == ""
        assert agent.role == ""
        assert agent.skills == []

    def test_missing_name(self):
        assert _parse_agent({"provider": "codex"}) is None

    def test_missing_provider(self):
        assert _parse_agent({"name": "bot"}) is None

    def test_empty_name(self):
        assert _parse_agent({"name": "", "provider": "codex"}) is None

    def test_not_a_dict(self):
        assert _parse_agent("invalid") is None
        assert _parse_agent(42) is None
        assert _parse_agent(None) is None

    def test_skills_filters_empty(self):
        raw = {"name": "bot", "provider": "gemini", "skills": ["python", "", "  ", "rust"]}
        agent = _parse_agent(raw)
        assert agent.skills == ["python", "rust"]

    def test_provider_lowered(self):
        raw = {"name": "bot", "provider": "Gemini"}
        agent = _parse_agent(raw)
        assert agent.provider == "gemini"


# ---------------------------------------------------------------------------
# _load_team_json
# ---------------------------------------------------------------------------

class TestLoadTeamJson:
    def test_missing_file(self, tmp_path: Path):
        assert _load_team_json(tmp_path / "nope.json") is None

    def test_valid_config(self, tmp_path: Path):
        f = tmp_path / "team.json"
        f.write_text(json.dumps({
            "name": "dev-team",
            "strategy": "skill_based",
            "agents": [
                {"name": "coder", "provider": "codex", "model": "o3", "role": "implementation"},
                {"name": "reviewer", "provider": "claude", "role": "review"},
            ],
        }))
        team = _load_team_json(f)
        assert team is not None
        assert team.name == "dev-team"
        assert team.strategy == "skill_based"
        assert len(team.agents) == 2

    def test_corrupt_json(self, tmp_path: Path):
        f = tmp_path / "bad.json"
        f.write_text("{invalid json")
        assert _load_team_json(f) is None

    def test_non_dict_json(self, tmp_path: Path):
        f = tmp_path / "arr.json"
        f.write_text(json.dumps([1, 2]))
        assert _load_team_json(f) is None

    def test_no_agents_returns_none(self, tmp_path: Path):
        f = tmp_path / "team.json"
        f.write_text(json.dumps({"name": "empty", "agents": []}))
        assert _load_team_json(f) is None

    def test_invalid_agents_skipped(self, tmp_path: Path):
        f = tmp_path / "team.json"
        f.write_text(json.dumps({
            "name": "partial",
            "agents": [
                {"name": "good", "provider": "codex"},
                {"name": "", "provider": "gemini"},  # invalid: empty name
                "not_a_dict",  # invalid: not dict
                {"provider": "claude"},  # invalid: no name
            ],
        }))
        team = _load_team_json(f)
        assert team is not None
        assert len(team.agents) == 1
        assert team.agents[0].name == "good"

    def test_default_name(self, tmp_path: Path):
        f = tmp_path / "team.json"
        f.write_text(json.dumps({"agents": [{"name": "a", "provider": "codex"}]}))
        team = _load_team_json(f)
        assert team.name == "default"

    def test_invalid_strategy_defaults(self, tmp_path: Path):
        f = tmp_path / "team.json"
        f.write_text(json.dumps({
            "name": "t",
            "strategy": "invalid_strategy",
            "agents": [{"name": "a", "provider": "codex"}],
        }))
        team = _load_team_json(f)
        assert team.strategy == "skill_based"

    def test_all_valid_strategies(self, tmp_path: Path):
        for strategy in VALID_STRATEGIES:
            f = tmp_path / f"team_{strategy}.json"
            f.write_text(json.dumps({
                "name": "t",
                "strategy": strategy,
                "agents": [{"name": "a", "provider": "codex"}],
            }))
            team = _load_team_json(f)
            assert team.strategy == strategy

    def test_description_field(self, tmp_path: Path):
        f = tmp_path / "team.json"
        f.write_text(json.dumps({
            "name": "t",
            "description": "My dev team",
            "agents": [{"name": "a", "provider": "codex"}],
        }))
        team = _load_team_json(f)
        assert team.description == "My dev team"


# ---------------------------------------------------------------------------
# load_team_config
# ---------------------------------------------------------------------------

class TestLoadTeamConfig:
    def test_no_config(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        assert load_team_config(work_dir=tmp_path) is None

    def test_global_config(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        ccb_dir = home / ".ccb"
        ccb_dir.mkdir(parents=True)
        (ccb_dir / "team.json").write_text(json.dumps({
            "name": "global-team",
            "agents": [{"name": "bot", "provider": "gemini"}],
        }))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        team = load_team_config(work_dir=tmp_path / "project")
        assert team is not None
        assert team.name == "global-team"

    def test_project_overrides_global(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        ccb_dir = home / ".ccb"
        ccb_dir.mkdir(parents=True)
        (ccb_dir / "team.json").write_text(json.dumps({
            "name": "global-team",
            "agents": [{"name": "bot", "provider": "gemini"}],
        }))

        proj = tmp_path / "project"
        proj_ccb = proj / ".ccb"
        proj_ccb.mkdir(parents=True)
        (proj_ccb / "team.json").write_text(json.dumps({
            "name": "project-team",
            "agents": [{"name": "coder", "provider": "codex"}],
        }))

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        team = load_team_config(work_dir=proj)
        assert team.name == "project-team"
        assert team.agents[0].name == "coder"

    def test_no_work_dir(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        ccb_dir = home / ".ccb"
        ccb_dir.mkdir(parents=True)
        (ccb_dir / "team.json").write_text(json.dumps({
            "name": "global",
            "agents": [{"name": "bot", "provider": "kimi"}],
        }))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        team = load_team_config(work_dir=None)
        assert team is not None
        assert team.name == "global"


# ---------------------------------------------------------------------------
# resolve_team_agent
# ---------------------------------------------------------------------------

class TestResolveTeamAgent:
    @pytest.fixture()
    def team(self) -> TeamConfig:
        return TeamConfig(
            name="dev",
            agents=[
                TeamAgent(name="researcher", provider="gemini", model="3f", role="research"),
                TeamAgent(name="coder", provider="codex", model="o3", role="implementation"),
                TeamAgent(name="reviewer", provider="claude", role="review"),
            ],
        )

    def test_resolve_known_agent(self, team):
        agent = resolve_team_agent("researcher", team)
        assert agent is not None
        assert agent.provider == "gemini"
        assert agent.model == "3f"

    def test_resolve_case_insensitive(self, team):
        agent = resolve_team_agent("Coder", team)
        assert agent is not None
        assert agent.provider == "codex"

    def test_resolve_unknown_returns_none(self, team):
        assert resolve_team_agent("unknown", team) is None

    def test_resolve_no_team(self):
        assert resolve_team_agent("coder", None) is None

    def test_resolve_empty_name(self, team):
        assert resolve_team_agent("", team) is None

    def test_resolve_none_name(self, team):
        assert resolve_team_agent(None, team) is None


# ---------------------------------------------------------------------------
# Integration: team agents override aliases
# ---------------------------------------------------------------------------

class TestTeamOverridesAlias:
    """Verify team agent names take priority over aliases."""

    def test_team_agent_overrides_alias(self):
        from aliases import DEFAULT_ALIASES, resolve_alias

        team = TeamConfig(
            name="test",
            agents=[TeamAgent(name="a", provider="kimi")],  # override alias a→codex
        )

        name = "a"
        # Team resolution first
        team_agent = resolve_team_agent(name, team)
        if team_agent:
            provider = team_agent.provider
        else:
            provider = resolve_alias(name, DEFAULT_ALIASES)

        assert provider == "kimi"  # team wins over alias

    def test_non_team_falls_to_alias(self):
        from aliases import DEFAULT_ALIASES, resolve_alias

        team = TeamConfig(
            name="test",
            agents=[TeamAgent(name="coder", provider="codex")],
        )

        name = "a"
        team_agent = resolve_team_agent(name, team)
        if team_agent:
            provider = team_agent.provider
        else:
            provider = resolve_alias(name, DEFAULT_ALIASES)

        assert provider == "codex"  # alias a→codex


# ---------------------------------------------------------------------------
# Full resolution flow (as in bin/ask)
# ---------------------------------------------------------------------------

class TestFullResolutionFlow:
    """Simulate the full resolution flow in bin/ask."""

    def _resolve(self, raw_provider: str, team: TeamConfig | None) -> tuple[str, str | None]:
        from aliases import load_aliases, resolve_alias
        from providers import parse_qualified_provider

        team_agent = resolve_team_agent(raw_provider, team)
        if team_agent:
            raw_provider = team_agent.provider
        else:
            aliases = {"a": "codex", "b": "gemini", "c": "claude"}
            base_part, _, instance_part = raw_provider.partition(":")
            base_part = resolve_alias(base_part, aliases)
            raw_provider = f"{base_part}:{instance_part}" if instance_part else base_part

        return parse_qualified_provider(raw_provider)

    def test_team_agent_resolves(self):
        team = TeamConfig(name="t", agents=[
            TeamAgent(name="researcher", provider="gemini", model="3f"),
        ])
        provider, instance = self._resolve("researcher", team)
        assert provider == "gemini"
        assert instance is None

    def test_alias_resolves_without_team(self):
        provider, instance = self._resolve("a", None)
        assert provider == "codex"

    def test_alias_with_instance(self):
        provider, instance = self._resolve("a:review", None)
        assert provider == "codex"
        assert instance == "review"

    def test_direct_provider(self):
        provider, instance = self._resolve("kimi", None)
        assert provider == "kimi"
        assert instance is None

    def test_team_agent_overrides_alias_letter(self):
        team = TeamConfig(name="t", agents=[
            TeamAgent(name="a", provider="qwen"),
        ])
        provider, instance = self._resolve("a", team)
        assert provider == "qwen"  # team wins
