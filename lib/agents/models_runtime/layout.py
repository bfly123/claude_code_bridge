from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


_LEAF_TOKEN_RE = re.compile(r'(?P<name>[A-Za-z][A-Za-z0-9_-]{0,31})(?:\s*:\s*(?P<provider>[A-Za-z0-9_-]+))?$')


@dataclass(frozen=True)
class LayoutLeaf:
    name: str
    provider: str | None = None


@dataclass(frozen=True)
class LayoutNode:
    kind: str
    leaf: LayoutLeaf | None = None
    left: 'LayoutNode | None' = None
    right: 'LayoutNode | None' = None

    def __post_init__(self) -> None:
        kind = str(self.kind or '').strip().lower()
        if kind not in {'leaf', 'horizontal', 'vertical'}:
            raise ValueError(f'unsupported layout node kind: {self.kind!r}')
        object.__setattr__(self, 'kind', kind)
        if kind == 'leaf':
            if self.leaf is None or self.left is not None or self.right is not None:
                raise ValueError('leaf layout node requires only leaf payload')
            return
        if self.leaf is not None or self.left is None or self.right is None:
            raise ValueError('branch layout node requires left/right children')

    @property
    def leaf_count(self) -> int:
        if self.kind == 'leaf':
            return 1
        assert self.left is not None
        assert self.right is not None
        return self.left.leaf_count + self.right.leaf_count

    def iter_leaves(self) -> tuple[LayoutLeaf, ...]:
        if self.kind == 'leaf':
            assert self.leaf is not None
            return (self.leaf,)
        assert self.left is not None
        assert self.right is not None
        return (*self.left.iter_leaves(), *self.right.iter_leaves())

    def render(self) -> str:
        if self.kind == 'leaf':
            assert self.leaf is not None
            if self.leaf.provider:
                return f'{self.leaf.name}:{self.leaf.provider}'
            return self.leaf.name
        assert self.left is not None
        assert self.right is not None
        sep = ';' if self.kind == 'horizontal' else ','
        left = _render_child(self.left, parent_kind=self.kind, is_right=False)
        right = _render_child(self.right, parent_kind=self.kind, is_right=True)
        return f'{left}{sep} {right}'


def _render_child(node: LayoutNode, *, parent_kind: str, is_right: bool) -> str:
    text = node.render()
    if node.kind == 'leaf':
        return text
    child_rank = _precedence(node.kind)
    parent_rank = _precedence(parent_kind)
    if child_rank < parent_rank:
        return f'({text})'
    if child_rank == parent_rank:
        return text
    if parent_kind == 'vertical' and node.kind == 'horizontal':
        return f'({text})'
    return text


def _precedence(kind: str) -> int:
    return {'horizontal': 1, 'vertical': 2, 'leaf': 3}[kind]


class LayoutParseError(ValueError):
    pass


class _LayoutParser:
    def __init__(self, text: str):
        self._tokens = _tokenize(text)
        self._index = 0

    def parse(self) -> LayoutNode:
        if not self._tokens:
            raise LayoutParseError('layout is empty')
        node = self._parse_horizontal()
        if self._peek() is not None:
            raise LayoutParseError(f'unexpected token {self._peek()!r}')
        return node

    def _parse_horizontal(self) -> LayoutNode:
        node = self._parse_vertical()
        while self._peek() == ';':
            self._consume(';')
            rhs = self._parse_vertical()
            node = LayoutNode(kind='horizontal', left=node, right=rhs)
        return node

    def _parse_vertical(self) -> LayoutNode:
        node = self._parse_primary()
        while self._peek() == ',':
            self._consume(',')
            rhs = self._parse_primary()
            node = LayoutNode(kind='vertical', left=node, right=rhs)
        return node

    def _parse_primary(self) -> LayoutNode:
        token = self._peek()
        if token is None:
            raise LayoutParseError('unexpected end of layout')
        if token == '(':
            self._consume('(')
            node = self._parse_horizontal()
            self._consume(')')
            return node
        if token in {')', ';', ','}:
            raise LayoutParseError(f'unexpected token {token!r}')
        leaf_token = self._consume_any()
        match = _LEAF_TOKEN_RE.fullmatch(leaf_token)
        if match is None:
            raise LayoutParseError(
                f"invalid layout token {leaf_token!r}; expected 'cmd', 'agent', or 'agent:provider'"
            )
        return LayoutNode(
            kind='leaf',
            leaf=LayoutLeaf(
                name=match.group('name').strip(),
                provider=(match.group('provider') or None),
            ),
        )

    def _peek(self) -> str | None:
        if self._index >= len(self._tokens):
            return None
        return self._tokens[self._index]

    def _consume(self, expected: str) -> str:
        token = self._peek()
        if token != expected:
            raise LayoutParseError(f'expected {expected!r}, found {token!r}')
        self._index += 1
        return token

    def _consume_any(self) -> str:
        token = self._peek()
        if token is None:
            raise LayoutParseError('unexpected end of layout')
        self._index += 1
        return token


def _tokenize(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    buf: list[str] = []
    for raw_line in str(text or '').splitlines():
        line = raw_line.split('#', 1)[0].split('//', 1)[0]
        for char in line:
            if char in {'(', ')', ';', ','}:
                leaf = ''.join(buf).strip()
                if leaf:
                    tokens.append(leaf)
                buf = []
                tokens.append(char)
                continue
            buf.append(char)
        leaf = ''.join(buf).strip()
        if leaf:
            tokens.append(leaf)
        buf = []
    return tuple(token for token in tokens if token)


def parse_layout_spec(text: str) -> LayoutNode:
    return _LayoutParser(text).parse()


def iter_layout_names(node: LayoutNode) -> tuple[str, ...]:
    return tuple(leaf.name for leaf in node.iter_leaves())


def prune_layout(node: LayoutNode, *, include_names: Iterable[str]) -> LayoutNode | None:
    include = {str(name).strip() for name in include_names if str(name).strip()}
    if node.kind == 'leaf':
        assert node.leaf is not None
        if node.leaf.name in include:
            return node
        return None
    assert node.left is not None
    assert node.right is not None
    left = prune_layout(node.left, include_names=include)
    right = prune_layout(node.right, include_names=include)
    if left is None:
        return right
    if right is None:
        return left
    return LayoutNode(kind=node.kind, left=left, right=right)


def build_balanced_layout(
    agent_names: Iterable[str],
    *,
    providers_by_agent: dict[str, str] | None = None,
    cmd_enabled: bool = False,
) -> LayoutNode:
    ordered_agents = [str(name).strip() for name in agent_names if str(name).strip()]
    if not ordered_agents:
        raise ValueError('at least one agent is required for layout')
    leaves: list[LayoutNode] = []
    providers = dict(providers_by_agent or {})
    if cmd_enabled:
        leaves.append(LayoutNode(kind='leaf', leaf=LayoutLeaf(name='cmd')))
    for name in ordered_agents:
        leaves.append(
            LayoutNode(
                kind='leaf',
                leaf=LayoutLeaf(name=name, provider=(providers.get(name) or None)),
            )
        )
    if len(leaves) == 1:
        return leaves[0]
    mid = (len(leaves) + 1) // 2
    left = _stack_vertical(leaves[:mid])
    right = _stack_vertical(leaves[mid:])
    if right is None:
        return left
    return LayoutNode(kind='horizontal', left=left, right=right)


def _stack_vertical(leaves: list[LayoutNode]) -> LayoutNode | None:
    if not leaves:
        return None
    node = leaves[0]
    for leaf in leaves[1:]:
        node = LayoutNode(kind='vertical', left=node, right=leaf)
    return node


__all__ = [
    'LayoutLeaf',
    'LayoutNode',
    'LayoutParseError',
    'build_balanced_layout',
    'iter_layout_names',
    'parse_layout_spec',
    'prune_layout',
]
