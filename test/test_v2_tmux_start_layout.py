from __future__ import annotations

from pathlib import Path

from agents.config_loader import load_project_config
from cli.context import CliContext
from cli.models import ParsedStartCommand
import cli.services.tmux_start_layout as tmux_start_layout
from project.resolver import bootstrap_project
from storage.paths import PathLayout


def _context(project_root: Path) -> CliContext:
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    project = bootstrap_project(project_root)
    command = ParsedStartCommand(project=None, agent_names=(), restore=False, auto_permission=False)
    return CliContext(command=command, cwd=project_root, project=project, paths=PathLayout(project_root))


def test_prepare_tmux_start_layout_uses_current_pane_as_cmd_anchor(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-layout'
    ctx = _context(project_root)
    config = load_project_config(project_root).config
    calls: list[tuple[str, str, str]] = []

    class FakeTmuxBackend:
        def get_current_pane_id(self) -> str:
            return '%0'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            calls.append(('title', pane_id, title))

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            calls.append((name, pane_id, value))

        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            mapping = {
                ('right', '%0'): '%1',
                ('bottom', '%0'): '%2',
                ('bottom', '%1'): '%3',
            }
            return mapping[(direction, str(parent_pane))]

    monkeypatch.setattr(tmux_start_layout, 'TmuxBackend', FakeTmuxBackend)

    layout = tmux_start_layout.prepare_tmux_start_layout(
        ctx,
        config=config,
        targets=('agent1', 'agent2', 'agent3'),
    )

    assert layout.cmd_pane_id == '%0'
    assert layout.agent_panes == {'agent1': '%2', 'agent2': '%1', 'agent3': '%3'}
    assert ('title', '%0', 'cmd') in calls
    assert ('title', '%2', 'agent1') in calls
    assert ('title', '%1', 'agent2') in calls
    assert ('title', '%3', 'agent3') in calls


def test_prepare_tmux_start_layout_assigns_ordered_styles(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-layout-styles'
    ctx = _context(project_root)
    config = load_project_config(project_root).config
    options: dict[tuple[str, str], str] = {}
    styles: dict[str, tuple[str | None, str | None]] = {}

    class FakeTmuxBackend:
        def get_current_pane_id(self) -> str:
            return '%0'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            return None

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            options[(pane_id, name)] = value

        def set_pane_style(
            self,
            pane_id: str,
            *,
            border_style: str | None = None,
            active_border_style: str | None = None,
        ) -> None:
            styles[pane_id] = (border_style, active_border_style)

        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            mapping = {
                ('right', '%0'): '%1',
                ('bottom', '%0'): '%2',
                ('bottom', '%1'): '%3',
            }
            return mapping[(direction, str(parent_pane))]

    monkeypatch.setattr(tmux_start_layout, 'TmuxBackend', FakeTmuxBackend)

    layout = tmux_start_layout.prepare_tmux_start_layout(
        ctx,
        config=config,
        targets=('agent1', 'agent2', 'agent3'),
    )

    assert layout.agent_panes == {'agent1': '%2', 'agent2': '%1', 'agent3': '%3'}
    assert options[('%0', '@ccb_label_style')] == '#[fg=#1e1e2e]#[bg=#7dcfff]#[bold]'
    assert options[('%2', '@ccb_label_style')] == '#[fg=#1e1e2e]#[bg=#ff9e64]#[bold]'
    assert options[('%1', '@ccb_label_style')] == '#[fg=#1e1e2e]#[bg=#9ece6a]#[bold]'
    assert options[('%3', '@ccb_label_style')] == '#[fg=#1e1e2e]#[bg=#f7768e]#[bold]'
    assert styles['%2'] == ('fg=#ff9e64', 'fg=#ff9e64,bold')
    assert styles['%1'] == ('fg=#9ece6a', 'fg=#9ece6a,bold')
    assert styles['%3'] == ('fg=#f7768e', 'fg=#f7768e,bold')


def test_prepare_tmux_start_layout_uses_root_pane_for_first_agent_when_cmd_disabled(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-layout-no-cmd'
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)
    (project_root / '.ccb' / 'ccb.config').write_text('demo:codex\n', encoding='utf-8')
    ctx = _context(project_root)
    config = load_project_config(project_root).config
    calls: list[tuple[str, str, str]] = []

    class FakeTmuxBackend:
        def get_current_pane_id(self) -> str:
            return '%0'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            calls.append(('title', pane_id, title))

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            calls.append((name, pane_id, value))

        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            raise AssertionError('single-agent no-cmd layout should reuse root pane')

    monkeypatch.setattr(tmux_start_layout, 'TmuxBackend', FakeTmuxBackend)

    layout = tmux_start_layout.prepare_tmux_start_layout(
        ctx,
        config=config,
        targets=('demo',),
    )

    assert layout.cmd_pane_id is None
    assert layout.agent_panes == {'demo': '%0'}
    assert ('title', '%0', 'demo') in calls
