from __future__ import annotations

from types import SimpleNamespace

import pytest

from cli.services.daemon_runtime.compat import shutdown_incompatible_daemon


def test_shutdown_incompatible_daemon_named_pipe_ignores_keyboard_interrupt_noise(monkeypatch) -> None:
    context = SimpleNamespace(paths=SimpleNamespace(ccbd_ipc_kind='named_pipe'))
    inspections = iter(
        (
            SimpleNamespace(socket_connectable=True, health='healthy'),
            SimpleNamespace(socket_connectable=False, health='missing'),
        )
    )
    sleep_calls: list[float] = []

    def _inspect(current_context):
        assert current_context is context
        inspection = next(inspections)
        return None, None, inspection

    def _sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        if len(sleep_calls) == 1:
            raise KeyboardInterrupt

    monkeypatch.setattr('cli.services.daemon_runtime.compat.time.sleep', _sleep)

    shutdown_incompatible_daemon(
        context,
        SimpleNamespace(shutdown=lambda: None),
        inspect_daemon_fn=_inspect,
        incompatible_daemon_error='incompatible daemon',
        shutdown_timeout_s=0.2,
        unavailable_health_states={'missing'},
    )

    assert len(sleep_calls) >= 1
    assert all(seconds > 0 for seconds in sleep_calls)


def test_shutdown_incompatible_daemon_non_named_pipe_still_propagates_keyboard_interrupt(monkeypatch) -> None:
    context = SimpleNamespace(paths=SimpleNamespace(ccbd_ipc_kind='unix_socket'))

    def _inspect(current_context):
        assert current_context is context
        return None, None, SimpleNamespace(socket_connectable=True, health='healthy')

    monkeypatch.setattr(
        'cli.services.daemon_runtime.compat.time.sleep',
        lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        shutdown_incompatible_daemon(
            context,
            SimpleNamespace(shutdown=lambda: None),
            inspect_daemon_fn=_inspect,
            incompatible_daemon_error='incompatible daemon',
            shutdown_timeout_s=0.2,
            unavailable_health_states={'missing'},
        )


def test_shutdown_incompatible_daemon_named_pipe_ignores_keyboard_interrupt_during_deadline_checks(monkeypatch) -> None:
    context = SimpleNamespace(paths=SimpleNamespace(ccbd_ipc_kind='named_pipe'))
    inspections = iter(
        (
            SimpleNamespace(socket_connectable=True, health='healthy'),
            SimpleNamespace(socket_connectable=False, health='missing'),
        )
    )
    original_monotonic = __import__('time').monotonic
    monotonic_calls = {'count': 0}

    def _inspect(current_context):
        assert current_context is context
        inspection = next(inspections)
        return None, None, inspection

    def _monotonic() -> float:
        monotonic_calls['count'] += 1
        if monotonic_calls['count'] == 1:
            raise KeyboardInterrupt
        return original_monotonic()

    monkeypatch.setattr('cli.services.daemon_runtime.compat.time.sleep', lambda seconds: None)
    monkeypatch.setattr('cli.services.daemon_runtime.compat.time.monotonic', _monotonic)

    shutdown_incompatible_daemon(
        context,
        SimpleNamespace(shutdown=lambda: None),
        inspect_daemon_fn=_inspect,
        incompatible_daemon_error='incompatible daemon',
        shutdown_timeout_s=0.2,
        unavailable_health_states={'missing'},
    )

    assert monotonic_calls['count'] >= 2
