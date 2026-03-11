"""Tests for lib/agent_comm.py — inter-agent communication."""

from __future__ import annotations

import pytest

from agent_comm import (
    AgentMessage,
    broadcast_message,
    build_chain_messages,
    parse_chain_spec,
    resolve_agent_to_provider,
    wrap_message,
)
from team_config import TeamAgent, TeamConfig


# ---------------------------------------------------------------------------
# AgentMessage
# ---------------------------------------------------------------------------

class TestAgentMessage:
    def test_basic(self):
        msg = AgentMessage(sender="codex", receiver="gemini", content="hello")
        assert msg.sender == "codex"
        assert msg.receiver == "gemini"
        assert msg.content == "hello"
        assert msg.context == ""

    def test_with_context(self):
        msg = AgentMessage(sender="a", receiver="b", content="review", context="prev output")
        assert msg.context == "prev output"


# ---------------------------------------------------------------------------
# wrap_message
# ---------------------------------------------------------------------------

class TestWrapMessage:
    def test_basic_wrap(self):
        msg = AgentMessage(sender="codex", receiver="gemini", content="hello")
        result = wrap_message(msg)
        assert "[CCB_FROM agent=codex]" in result
        assert "hello" in result
        assert "[CCB_CONTEXT]" not in result

    def test_wrap_with_context(self):
        msg = AgentMessage(sender="a", receiver="b", content="review this", context="code here")
        result = wrap_message(msg)
        assert "[CCB_FROM agent=a]" in result
        assert "[CCB_CONTEXT]" in result
        assert "code here" in result
        assert "[/CCB_CONTEXT]" in result
        assert "review this" in result

    def test_wrap_order(self):
        msg = AgentMessage(sender="x", receiver="y", content="task", context="ctx")
        result = wrap_message(msg)
        lines = result.split("\n")
        # First line should be FROM
        assert lines[0] == "[CCB_FROM agent=x]"
        # Last line should be content
        assert lines[-1] == "task"


# ---------------------------------------------------------------------------
# resolve_agent_to_provider
# ---------------------------------------------------------------------------

class TestResolveAgentToProvider:
    @pytest.fixture()
    def team(self) -> TeamConfig:
        return TeamConfig(
            name="test",
            agents=[
                TeamAgent(name="researcher", provider="gemini"),
                TeamAgent(name="coder", provider="codex"),
            ],
        )

    def test_team_agent(self, team):
        aliases = {"a": "codex"}
        assert resolve_agent_to_provider("researcher", team, aliases) == "gemini"

    def test_alias(self, team):
        aliases = {"a": "codex", "b": "gemini"}
        assert resolve_agent_to_provider("a", None, aliases) == "codex"

    def test_team_over_alias(self, team):
        aliases = {"researcher": "kimi"}  # alias would give kimi
        # Team agent should win
        assert resolve_agent_to_provider("researcher", team, aliases) == "gemini"

    def test_direct_provider(self):
        aliases = {}
        assert resolve_agent_to_provider("kimi", None, aliases) == "kimi"

    def test_empty_name(self):
        assert resolve_agent_to_provider("", None, {}) is None

    def test_none_name(self):
        assert resolve_agent_to_provider(None, None, {}) is None

    def test_case_insensitive(self, team):
        aliases = {}
        assert resolve_agent_to_provider("Researcher", team, aliases) == "gemini"


# ---------------------------------------------------------------------------
# broadcast_message
# ---------------------------------------------------------------------------

class TestBroadcastMessage:
    @pytest.fixture()
    def team(self) -> TeamConfig:
        return TeamConfig(
            name="dev",
            agents=[
                TeamAgent(name="a", provider="codex"),
                TeamAgent(name="b", provider="gemini"),
                TeamAgent(name="c", provider="claude"),
            ],
        )

    def test_broadcast_excludes_sender(self, team):
        msgs = broadcast_message("a", "hello everyone", team, exclude_sender=True)
        assert len(msgs) == 2
        receivers = [m.receiver for m in msgs]
        assert "codex" not in receivers  # sender excluded
        assert "gemini" in receivers
        assert "claude" in receivers

    def test_broadcast_includes_sender(self, team):
        msgs = broadcast_message("a", "hello", team, exclude_sender=False)
        assert len(msgs) == 3

    def test_broadcast_content(self, team):
        msgs = broadcast_message("a", "sync up", team)
        for m in msgs:
            assert m.content == "sync up"
            assert m.sender == "a"

    def test_broadcast_empty_team(self):
        team = TeamConfig(name="empty", agents=[])
        msgs = broadcast_message("a", "hello", team)
        assert msgs == []

    def test_broadcast_sender_not_in_team(self, team):
        msgs = broadcast_message("external", "hello", team)
        assert len(msgs) == 3  # all agents receive


# ---------------------------------------------------------------------------
# parse_chain_spec
# ---------------------------------------------------------------------------

class TestParseChainSpec:
    def test_basic_chain(self):
        result = parse_chain_spec("a:research | b:implement | c:review")
        assert result == [("a", "research"), ("b", "implement"), ("c", "review")]

    def test_single_step(self):
        result = parse_chain_spec("codex:write code")
        assert result == [("codex", "write code")]

    def test_empty_string(self):
        assert parse_chain_spec("") == []

    def test_whitespace_handling(self):
        result = parse_chain_spec("  a : task1  |  b : task2  ")
        assert result == [("a", "task1"), ("b", "task2")]

    def test_no_colon_skips(self):
        # Segment without colon: agent is empty, treated as task only
        result = parse_chain_spec("just a task")
        assert result == [("", "just a task")]

    def test_mixed_valid_invalid(self):
        result = parse_chain_spec("a:task1 | | b:task2")
        assert result == [("a", "task1"), ("b", "task2")]

    def test_empty_agent_after_colon(self):
        result = parse_chain_spec(":task")
        assert result == []  # empty agent


# ---------------------------------------------------------------------------
# build_chain_messages
# ---------------------------------------------------------------------------

class TestBuildChainMessages:
    def test_basic_chain(self):
        chain = [("gemini", "research"), ("codex", "implement"), ("claude", "review")]
        msgs = build_chain_messages(chain)
        assert len(msgs) == 3

        assert msgs[0].sender == "user"
        assert msgs[0].receiver == "gemini"
        assert msgs[0].content == "research"

        assert msgs[1].sender == "gemini"
        assert msgs[1].receiver == "codex"
        assert msgs[1].content == "implement"

        assert msgs[2].sender == "codex"
        assert msgs[2].receiver == "claude"
        assert msgs[2].content == "review"

    def test_single_step(self):
        msgs = build_chain_messages([("codex", "do it")])
        assert len(msgs) == 1
        assert msgs[0].sender == "user"
        assert msgs[0].receiver == "codex"

    def test_empty_chain(self):
        assert build_chain_messages([]) == []


# ---------------------------------------------------------------------------
# Integration: --to flow simulation
# ---------------------------------------------------------------------------

class TestToFlowIntegration:
    """Simulate the --to flow as implemented in bin/ask."""

    def test_to_resolves_and_wraps(self):
        team = TeamConfig(name="t", agents=[
            TeamAgent(name="reviewer", provider="claude"),
        ])
        aliases = {"a": "codex"}

        sender = "codex"
        to_agent = "reviewer"
        message = "please review this code"

        target = resolve_agent_to_provider(to_agent, team, aliases)
        assert target == "claude"

        msg = AgentMessage(sender=sender, receiver=target, content=message)
        wrapped = wrap_message(msg)
        assert "[CCB_FROM agent=codex]" in wrapped
        assert "please review this code" in wrapped

    def test_to_with_alias(self):
        aliases = {"a": "codex", "b": "gemini"}

        target = resolve_agent_to_provider("b", None, aliases)
        assert target == "gemini"

    def test_chain_then_wrap(self):
        chain = [("gemini", "research topic"), ("codex", "implement")]
        msgs = build_chain_messages(chain)

        # Verify each step wraps correctly
        for msg in msgs:
            wrapped = wrap_message(msg)
            assert f"[CCB_FROM agent={msg.sender}]" in wrapped
            assert msg.content in wrapped


# ---------------------------------------------------------------------------
# Chain CLI flow simulation
# ---------------------------------------------------------------------------

class TestChainFlowIntegration:
    """Simulate the --chain flow as implemented in bin/ask."""

    def test_chain_resolves_agents(self):
        """Verify each step in a chain resolves to valid providers."""
        team = TeamConfig(name="t", agents=[
            TeamAgent(name="researcher", provider="gemini"),
            TeamAgent(name="coder", provider="codex"),
            TeamAgent(name="reviewer", provider="claude"),
        ])
        aliases = {"a": "codex"}

        spec = "researcher:analyze | coder:implement | reviewer:check"
        steps = parse_chain_spec(spec)
        msgs = build_chain_messages(steps)

        for msg in msgs:
            target = resolve_agent_to_provider(msg.receiver, team, aliases)
            assert target is not None, f"Failed to resolve: {msg.receiver}"

    def test_chain_context_passing(self):
        """Verify context from previous step is included in wrapped message."""
        msg = AgentMessage(
            sender="gemini", receiver="codex",
            content="implement this",
            context="Research result: use quicksort",
        )
        wrapped = wrap_message(msg)
        assert "[CCB_FROM agent=gemini]" in wrapped
        assert "[CCB_CONTEXT]" in wrapped
        assert "Research result: use quicksort" in wrapped
        assert "implement this" in wrapped

    def test_chain_with_aliases(self):
        """Verify aliases work in chain specs."""
        aliases = {"a": "codex", "b": "gemini"}
        steps = parse_chain_spec("b:research | a:implement")
        msgs = build_chain_messages(steps)

        target0 = resolve_agent_to_provider(msgs[0].receiver, None, aliases)
        target1 = resolve_agent_to_provider(msgs[1].receiver, None, aliases)
        assert target0 == "gemini"
        assert target1 == "codex"
