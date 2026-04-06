from __future__ import annotations

import pytest

from agents.models import build_balanced_layout, iter_layout_names, parse_layout_spec, prune_layout


def test_parse_layout_spec_roundtrip_with_parentheses() -> None:
    layout = parse_layout_spec('cmd; (agent1:codex, agent2:claude)')

    assert layout.render() == 'cmd; agent1:codex, agent2:claude'
    assert iter_layout_names(layout) == ('cmd', 'agent1', 'agent2')


def test_prune_layout_preserves_branch_shape_when_possible() -> None:
    layout = parse_layout_spec('cmd; (agent1:codex, agent2:claude)')

    pruned = prune_layout(layout, include_names=('cmd', 'agent2'))

    assert pruned is not None
    assert pruned.render() == 'cmd; agent2:claude'


def test_build_balanced_layout_adds_cmd_leaf_first() -> None:
    layout = build_balanced_layout(
        ('agent1', 'agent2', 'agent3'),
        providers_by_agent={'agent1': 'codex', 'agent2': 'claude', 'agent3': 'gemini'},
        cmd_enabled=True,
    )

    assert layout.render() == 'cmd, agent1:codex; agent2:claude, agent3:gemini'


def test_parse_layout_spec_rejects_invalid_leaf_token() -> None:
    with pytest.raises(Exception, match='invalid layout token'):
        parse_layout_spec('cmd; ???')
