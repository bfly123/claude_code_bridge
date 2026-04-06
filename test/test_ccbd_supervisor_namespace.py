from __future__ import annotations

from ccbd.supervisor_runtime.namespace import ensure_project_namespace


def test_ensure_project_namespace_calls_plain_ensure_when_no_namespace_kwargs_needed() -> None:
    calls: list[dict[str, object]] = []

    class _Namespace:
        def ensure(self):
            calls.append({})
            return 'ok'

    result = ensure_project_namespace(
        _Namespace(),
        layout_signature=None,
        recreate_namespace=False,
        recreate_reason=None,
    )

    assert result == 'ok'
    assert calls == [{}]


def test_ensure_project_namespace_passes_kwargs_when_supported() -> None:
    calls: list[dict[str, object]] = []

    class _Namespace:
        def ensure(self, *, layout_signature=None, force_recreate=False, recreate_reason=None):
            calls.append(
                {
                    'layout_signature': layout_signature,
                    'force_recreate': force_recreate,
                    'recreate_reason': recreate_reason,
                }
            )
            return 'ok'

    result = ensure_project_namespace(
        _Namespace(),
        layout_signature='cmd;agent1',
        recreate_namespace=True,
        recreate_reason='layout_changed',
    )

    assert result == 'ok'
    assert calls == [
        {
            'layout_signature': 'cmd;agent1',
            'force_recreate': True,
            'recreate_reason': 'layout_changed',
        }
    ]


def test_ensure_project_namespace_falls_back_when_signature_rejects_kwargs() -> None:
    calls: list[str] = []

    class _Namespace:
        def ensure(self):
            calls.append('plain')
            return 'ok'

    result = ensure_project_namespace(
        _Namespace(),
        layout_signature='cmd;agent1',
        recreate_namespace=False,
        recreate_reason='layout_changed',
    )

    assert result == 'ok'
    assert calls == ['plain']
