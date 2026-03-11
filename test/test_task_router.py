"""Tests for lib/task_router.py — smart task routing."""

from __future__ import annotations

import pytest

from task_router import (
    DEFAULT_FALLBACK,
    DEFAULT_ROUTING_RULES,
    RouteResult,
    RoutingRule,
    auto_route,
    route_by_keywords,
    route_by_team,
    _score_message,
    _score_agent_skills,
)
from team_config import TeamAgent, TeamConfig


# ---------------------------------------------------------------------------
# _score_message
# ---------------------------------------------------------------------------

class TestScoreMessage:
    def test_single_match(self):
        assert _score_message("build a React component", ["react"]) == 1.0

    def test_multiple_matches(self):
        assert _score_message("React CSS HTML frontend", ["react", "css", "html"]) == 3.0

    def test_no_match(self):
        assert _score_message("hello world", ["react", "vue"]) == 0.0

    def test_case_insensitive(self):
        assert _score_message("Build React UI", ["react", "ui"]) == 2.0

    def test_chinese_keywords(self):
        assert _score_message("帮我写一个前端组件", ["前端"]) == 1.0

    def test_empty_message(self):
        assert _score_message("", ["react"]) == 0.0


# ---------------------------------------------------------------------------
# route_by_keywords
# ---------------------------------------------------------------------------

class TestRouteByKeywords:
    def test_frontend_keywords(self):
        result = route_by_keywords("帮我写一个 React 前端组件")
        assert result.provider == "gemini"

    def test_algorithm_keywords(self):
        result = route_by_keywords("分析这个算法的时间复杂度")
        assert result.provider == "codex"

    def test_review_keywords(self):
        result = route_by_keywords("请审查这段代码的安全性")
        assert result.provider == "codex"

    def test_chinese_writing(self):
        result = route_by_keywords("翻译这段话成英文")
        assert result.provider == "kimi"

    def test_python_coding(self):
        result = route_by_keywords("用 Python 实现一个快排")
        assert result.provider == "qwen"

    def test_architecture(self):
        result = route_by_keywords("帮我重构这个架构设计模式")
        assert result.provider == "claude"

    def test_no_match_uses_fallback(self):
        result = route_by_keywords("hello world 123")
        assert result.provider == DEFAULT_FALLBACK.provider

    def test_empty_message_uses_fallback(self):
        result = route_by_keywords("")
        assert result.provider == DEFAULT_FALLBACK.provider

    def test_custom_rules(self):
        rules = [RoutingRule(provider="custom", model="v1", keywords=["magic"], weight=1.0)]
        result = route_by_keywords("do magic stuff", rules=rules)
        assert result.provider == "custom"
        assert result.model == "v1"

    def test_custom_fallback(self):
        fb = RouteResult(provider="fallback_provider", reason="custom fb")
        result = route_by_keywords("no match", rules=[], fallback=fb)
        assert result.provider == "fallback_provider"

    def test_higher_weight_wins(self):
        rules = [
            RoutingRule(provider="low", model="", keywords=["code"], weight=0.5),
            RoutingRule(provider="high", model="", keywords=["code"], weight=2.0),
        ]
        result = route_by_keywords("write code", rules=rules)
        assert result.provider == "high"

    def test_more_matches_wins(self):
        rules = [
            RoutingRule(provider="one_match", model="", keywords=["react"], weight=1.0),
            RoutingRule(provider="two_matches", model="", keywords=["react", "css"], weight=1.0),
        ]
        result = route_by_keywords("build React with CSS", rules=rules)
        assert result.provider == "two_matches"

    def test_reason_includes_keywords(self):
        result = route_by_keywords("帮我写 React 前端")
        assert "keywords:" in result.reason

    def test_score_is_positive(self):
        result = route_by_keywords("用 React 写前端")
        assert result.score > 0


# ---------------------------------------------------------------------------
# _score_agent_skills
# ---------------------------------------------------------------------------

class TestScoreAgentSkills:
    def test_skill_match(self):
        agent = TeamAgent(name="dev", provider="codex", skills=["python", "rust"])
        assert _score_agent_skills(agent, "write python code") == 1.5

    def test_role_match(self):
        agent = TeamAgent(name="dev", provider="codex", role="review")
        assert _score_agent_skills(agent, "please review this") == 1.0

    def test_skill_and_role_match(self):
        agent = TeamAgent(name="dev", provider="codex", role="review", skills=["security"])
        score = _score_agent_skills(agent, "security review needed")
        assert score == 2.5  # 1.5 (skill) + 1.0 (role)

    def test_no_match(self):
        agent = TeamAgent(name="dev", provider="codex", skills=["python"])
        assert _score_agent_skills(agent, "write rust code") == 0.0

    def test_no_skills_no_role(self):
        agent = TeamAgent(name="dev", provider="codex")
        assert _score_agent_skills(agent, "anything") == 0.0


# ---------------------------------------------------------------------------
# route_by_team
# ---------------------------------------------------------------------------

class TestRouteByTeam:
    @pytest.fixture()
    def team(self) -> TeamConfig:
        return TeamConfig(
            name="dev-team",
            agents=[
                TeamAgent(name="frontend", provider="gemini", model="3f", role="research", skills=["react", "css", "frontend"]),
                TeamAgent(name="backend", provider="codex", model="o3", role="implementation", skills=["python", "api", "database"]),
                TeamAgent(name="reviewer", provider="claude", role="review", skills=["security", "architecture"]),
            ],
        )

    def test_frontend_task(self, team):
        result = route_by_team("build a React frontend component", team)
        assert result is not None
        assert result.provider == "gemini"
        assert "team:frontend" in result.reason

    def test_backend_task(self, team):
        result = route_by_team("implement Python API with database", team)
        assert result is not None
        assert result.provider == "codex"

    def test_review_task(self, team):
        result = route_by_team("security review of the architecture", team)
        assert result is not None
        assert result.provider == "claude"

    def test_no_match(self, team):
        result = route_by_team("hello world", team)
        assert result is None

    def test_empty_message(self, team):
        assert route_by_team("", team) is None

    def test_empty_team(self):
        team = TeamConfig(name="empty", agents=[])
        assert route_by_team("anything", team) is None

    def test_best_agent_wins(self, team):
        # "python api" matches backend (2 skills), not frontend
        result = route_by_team("python api endpoint", team)
        assert result is not None
        assert result.provider == "codex"

    def test_score_is_positive(self, team):
        result = route_by_team("react frontend", team)
        assert result is not None
        assert result.score > 0


# ---------------------------------------------------------------------------
# auto_route
# ---------------------------------------------------------------------------

class TestAutoRoute:
    @pytest.fixture()
    def team(self) -> TeamConfig:
        return TeamConfig(
            name="dev-team",
            agents=[
                TeamAgent(name="fe", provider="gemini", skills=["react", "frontend"]),
                TeamAgent(name="be", provider="codex", skills=["python", "api"]),
            ],
        )

    def test_team_match_preferred(self, team):
        result = auto_route("build react frontend", team)
        assert result.provider == "gemini"
        assert "team:" in result.reason

    def test_falls_to_keywords_when_no_team_match(self, team):
        result = auto_route("翻译这段话", team)
        assert result.provider == "kimi"  # keyword match, not team

    def test_falls_to_keywords_without_team(self):
        result = auto_route("React 前端组件")
        assert result.provider == "gemini"

    def test_falls_to_fallback(self):
        result = auto_route("hello there")
        assert result.provider == DEFAULT_FALLBACK.provider

    def test_no_team_uses_keywords(self):
        result = auto_route("分析算法复杂度", None)
        assert result.provider == "codex"

    def test_empty_message(self):
        result = auto_route("")
        assert result.provider == DEFAULT_FALLBACK.provider


# ---------------------------------------------------------------------------
# Integration: full ask --auto flow simulation
# ---------------------------------------------------------------------------

class TestAutoRouteIntegration:
    """Simulate the full --auto flow as implemented in bin/ask."""

    def _simulate_auto(self, message: str, team: TeamConfig | None = None) -> str:
        route = auto_route(message, team)
        return route.provider

    def test_auto_frontend(self):
        assert self._simulate_auto("帮我写一个 React 前端组件") == "gemini"

    def test_auto_algorithm(self):
        assert self._simulate_auto("分析这个算法的时间复杂度") == "codex"

    def test_auto_translation(self):
        assert self._simulate_auto("翻译这段话成英文") == "kimi"

    def test_auto_python(self):
        assert self._simulate_auto("用 Python 实现快排") == "qwen"

    def test_auto_review(self):
        assert self._simulate_auto("请审查这段代码") == "codex"

    def test_auto_with_team(self):
        team = TeamConfig(name="t", agents=[
            TeamAgent(name="fe", provider="qwen", skills=["react", "frontend"]),
        ])
        # Team skill match overrides keyword match
        assert self._simulate_auto("build react frontend", team) == "qwen"

    def test_auto_team_no_match_falls_to_keywords(self):
        team = TeamConfig(name="t", agents=[
            TeamAgent(name="fe", provider="qwen", skills=["react"]),
        ])
        assert self._simulate_auto("分析算法复杂度", team) == "codex"
