from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import cli.services.tmux_ui as tmux_ui


def test_set_tmux_ui_active_runs_expected_script(monkeypatch, tmp_path: Path) -> None:
    bin_dir = tmp_path / '.local' / 'bin'
    bin_dir.mkdir(parents=True)
    on_script = bin_dir / 'ccb-tmux-on.sh'
    off_script = bin_dir / 'ccb-tmux-off.sh'
    on_script.write_text('#!/bin/sh\n', encoding='utf-8')
    off_script.write_text('#!/bin/sh\n', encoding='utf-8')

    calls: list[list[str]] = []

    monkeypatch.setenv('TMUX', '/tmp/tmux-1/default,123,0')
    monkeypatch.setattr(tmux_ui.Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(tmux_ui.subprocess, 'run', lambda args, **kwargs: calls.append(list(args)))

    tmux_ui.set_tmux_ui_active(True)
    tmux_ui.set_tmux_ui_active(False)

    assert calls == [[str(on_script)], [str(off_script)]]


def test_set_tmux_ui_active_skips_outside_tmux(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    monkeypatch.delenv('TMUX', raising=False)
    monkeypatch.delenv('TMUX_PANE', raising=False)
    monkeypatch.setattr(tmux_ui.Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(tmux_ui.subprocess, 'run', lambda args, **kwargs: calls.append(list(args)))

    tmux_ui.set_tmux_ui_active(True)

    assert calls == []


def test_apply_project_tmux_ui_sets_session_theme_and_hook(monkeypatch, tmp_path: Path) -> None:
    bin_dir = tmp_path / '.local' / 'bin'
    bin_dir.mkdir(parents=True)
    for script_name in ('ccb-status.sh', 'ccb-border.sh', 'ccb-git.sh'):
        (bin_dir / script_name).write_text('#!/bin/sh\n', encoding='utf-8')
    (bin_dir / 'ccb').write_text('VERSION = "9.9.9"\n', encoding='utf-8')

    calls: list[list[str]] = []

    class FakeBackend:
        def _tmux_run(self, args, *, check=False, capture=False):
            del check
            calls.append(list(args))
            if capture and args[:4] == ['list-panes', '-t', 'ccb-demo', '-F']:
                return SimpleNamespace(returncode=0, stdout='\n%9\n', stderr='')
            if capture and args[:4] == ['display-message', '-p', '-t', '%9']:
                if args[4] == '#{@ccb_active_border_style}':
                    return SimpleNamespace(returncode=0, stdout='fg=#f7768e,bold\n', stderr='')
                return SimpleNamespace(returncode=0, stdout='', stderr='')
            return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr(tmux_ui.Path, 'home', classmethod(lambda cls: tmp_path))

    tmux_ui.apply_project_tmux_ui(
        tmux_socket_path='/tmp/ccb.sock',
        tmux_session_name='ccb-demo',
        backend=FakeBackend(),
    )

    assert ['set-option', '-t', 'ccb-demo', '@ccb_version', '9.9.9'] in calls
    assert ['set-window-option', '-t', 'ccb-demo', 'pane-border-status', 'top'] in calls
    assert ['set-window-option', '-t', 'ccb-demo', 'pane-border-style', 'fg=#3b4261,bold'] in calls
    assert ['set-window-option', '-t', 'ccb-demo', 'pane-active-border-style', 'fg=#7aa2f7,bold'] in calls
    assert any(
        call[:4] == ['set-window-option', '-t', 'ccb-demo', 'pane-border-format']
        for call in calls
    )
    assert any(
        call[:4] == ['set-hook', '-t', 'ccb-demo', 'after-select-pane']
        and 'ccb-border.sh' in call[4]
        for call in calls
    )
    assert ['set-option', '-p', '-t', '%9', 'pane-active-border-style', 'fg=#f7768e,bold'] in calls
