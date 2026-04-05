from __future__ import annotations

from io import StringIO
import os

from launcher.target_router import LauncherTargetRouter


def test_target_router_dispatches_tmux_provider(monkeypatch) -> None:
    calls: list[tuple[str | None, str | None]] = []
    monkeypatch.setenv('TMUX', '/tmp/tmux-1000/default,1,0')
    monkeypatch.setattr('launcher.target_router.shutil.which', lambda name: '/usr/bin/tmux' if name == 'tmux' else None)
    router = LauncherTargetRouter(
        terminal_type='tmux',
        target_tmux_starters={'gemini': lambda parent_pane=None, direction=None: calls.append((parent_pane, direction)) or '%9'},
        translate_fn=lambda key, **kwargs: key,
        stderr=StringIO(),
    )

    pane_id = router.start('gemini', parent_pane='%1', direction='bottom')

    assert pane_id == '%9'
    assert calls == [('%1', 'bottom')]
