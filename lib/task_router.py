"""Smart task routing for CCB Agent Teams.

Routes tasks to the best provider based on message content analysis.
Supports keyword matching (Chinese + English) and team skill-based matching.

Used by `ask --auto "message"` to auto-select the best provider.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from team_config import TeamAgent, TeamConfig


@dataclass
class RouteResult:
    """Result of routing a task to a provider."""
    provider: str
    model: str = ""
    reason: str = ""
    score: float = 0.0


# ---------------------------------------------------------------------------
# Keyword → provider routing rules
# ---------------------------------------------------------------------------

@dataclass
class RoutingRule:
    """A keyword-based routing rule."""
    provider: str
    model: str
    keywords: List[str]
    weight: float = 1.0


# Default routing rules (reference: HiveMind ProviderRouter + CLAUDE.md mapping)
DEFAULT_ROUTING_RULES: List[RoutingRule] = [
    RoutingRule(
        provider="gemini", model="3f",
        keywords=["frontend", "前端", "react", "vue", "css", "html", "ui", "design", "设计", "样式", "组件", "tailwind", "nextjs"],
        weight=1.5,
    ),
    RoutingRule(
        provider="codex", model="o3",
        keywords=["algorithm", "算法", "math", "数学", "proof", "证明", "reasoning", "推理", "逻辑", "logic", "complexity", "复杂度"],
        weight=1.5,
    ),
    RoutingRule(
        provider="codex", model="o3",
        keywords=["review", "审查", "审核", "audit", "security", "安全", "code review", "代码审查"],
        weight=1.5,
    ),
    RoutingRule(
        provider="qwen", model="",
        keywords=["python", "编程", "代码生成", "code", "coding", "implement", "实现", "sql", "database", "数据库", "数据分析"],
        weight=1.0,
    ),
    RoutingRule(
        provider="kimi", model="thinking",
        keywords=["中文", "chinese", "翻译", "translate", "translation", "文案", "写作", "writing", "长文", "文档", "document", "总结", "summary", "分析"],
        weight=1.0,
    ),
    RoutingRule(
        provider="kimi", model="",
        keywords=["explain", "解释", "概念", "concept", "快速", "quick", "shell", "bash", "运维", "devops"],
        weight=0.8,
    ),
    RoutingRule(
        provider="claude", model="",
        keywords=["architecture", "架构", "设计模式", "design pattern", "重构", "refactor", "planning", "规划"],
        weight=1.0,
    ),
]

# Default fallback when no keywords match
DEFAULT_FALLBACK = RouteResult(provider="kimi", model="", reason="default fallback", score=0.0)


def _score_message(message: str, keywords: List[str]) -> float:
    """Score a message against a list of keywords. Returns number of matches."""
    text = message.lower()
    score = 0.0
    for kw in keywords:
        if kw.lower() in text:
            score += 1.0
    return score


def route_by_keywords(
    message: str,
    rules: Optional[List[RoutingRule]] = None,
    fallback: Optional[RouteResult] = None,
) -> RouteResult:
    """Route a message to a provider based on keyword matching.

    Returns the RouteResult with the highest weighted score.
    """
    if rules is None:
        rules = DEFAULT_ROUTING_RULES
    if fallback is None:
        fallback = DEFAULT_FALLBACK

    if not message or not message.strip():
        return fallback

    best: Optional[RouteResult] = None
    best_score = 0.0

    for rule in rules:
        raw_score = _score_message(message, rule.keywords)
        if raw_score <= 0:
            continue
        weighted = raw_score * rule.weight
        if weighted > best_score:
            best_score = weighted
            matched = [kw for kw in rule.keywords if kw.lower() in message.lower()]
            best = RouteResult(
                provider=rule.provider,
                model=rule.model,
                reason=f"keywords: {', '.join(matched[:3])}",
                score=weighted,
            )

    return best if best else fallback


# ---------------------------------------------------------------------------
# Team skill-based routing
# ---------------------------------------------------------------------------

def _score_agent_skills(agent: TeamAgent, message: str) -> float:
    """Score a team agent against a message based on skills + role keywords."""
    if not agent.skills and not agent.role:
        return 0.0
    text = message.lower()
    score = 0.0
    for skill in agent.skills:
        if skill in text:
            score += 1.5  # skills are more specific, higher weight
    if agent.role and agent.role in text:
        score += 1.0
    return score


def route_by_team(
    message: str,
    team: TeamConfig,
) -> Optional[RouteResult]:
    """Route a message to the best team agent based on skills and role matching.

    Returns None if no agent has a positive match score.
    """
    if not message or not message.strip() or not team.agents:
        return None

    best_agent: Optional[TeamAgent] = None
    best_score = 0.0

    for agent in team.agents:
        score = _score_agent_skills(agent, message)
        if score > best_score:
            best_score = score
            best_agent = agent

    if best_agent is None:
        return None

    matched = []
    text = message.lower()
    for s in best_agent.skills:
        if s in text:
            matched.append(s)
    if best_agent.role and best_agent.role in text:
        matched.append(f"role:{best_agent.role}")

    return RouteResult(
        provider=best_agent.provider,
        model=best_agent.model,
        reason=f"team:{best_agent.name} ({', '.join(matched[:3])})",
        score=best_score,
    )


# ---------------------------------------------------------------------------
# Unified auto-route
# ---------------------------------------------------------------------------

def auto_route(
    message: str,
    team: Optional[TeamConfig] = None,
) -> RouteResult:
    """Auto-route a message to the best provider.

    Resolution order:
    1. Team skill-based matching (if team config exists)
    2. Keyword-based matching (default rules)
    3. Default fallback
    """
    # Try team-based routing first
    if team is not None:
        result = route_by_team(message, team)
        if result:
            return result

    # Fall back to keyword-based routing
    return route_by_keywords(message)
