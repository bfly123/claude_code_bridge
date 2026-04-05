from __future__ import annotations

from launcher.current_pane_router import LauncherCurrentPaneRouter


def test_current_pane_router_dispatches_provider() -> None:
    calls: list[str] = []
    router = LauncherCurrentPaneRouter(translate_fn=lambda key, **kwargs: key)

    rc = router.start(
        'codex',
        starters={
            'codex': lambda: calls.append('codex') or 0,
            'gemini': lambda: calls.append('gemini') or 0,
        },
    )

    assert rc == 0
    assert calls == ['codex']


def test_current_pane_router_reports_unknown_provider(capsys) -> None:
    router = LauncherCurrentPaneRouter(
        translate_fn=lambda key, **kwargs: f"{key}:{kwargs.get('provider')}"
    )

    rc = router.start('unknown', starters={})

    assert rc == 1
    assert 'unknown_provider:unknown' in capsys.readouterr().out
