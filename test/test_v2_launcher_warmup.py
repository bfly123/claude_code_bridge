from __future__ import annotations

from launcher.warmup import LauncherWarmupService


def test_warmup_service_returns_true_for_gemini_without_probe() -> None:
    service = LauncherWarmupService()

    assert service.warmup_provider('gemini') is True


def test_warmup_service_retries_until_success() -> None:
    attempts: list[str] = []
    sleeps: list[float] = []
    outputs: list[str] = []
    now = {'value': 0.0}

    def probe_fn(provider: str):
        attempts.append(provider)
        if len(attempts) < 3:
            return False, 'not ready'
        return True, 'ready'

    service = LauncherWarmupService(
        probe_fn=probe_fn,
        sleep_fn=lambda seconds: sleeps.append(seconds) or now.__setitem__('value', now['value'] + seconds),
        time_fn=lambda: now['value'],
        print_fn=outputs.append,
    )

    assert service.warmup_provider('codex', timeout=2.0) is True
    assert attempts == ['codex', 'codex', 'codex']
    assert sleeps == [0.3, 0.44999999999999996]
    assert outputs[0] == '🔧 Warmup: codex'
    assert outputs[-1] == 'ready'


def test_warmup_service_reports_failure_output() -> None:
    outputs: list[str] = []
    now = {'value': 0.0}

    service = LauncherWarmupService(
        probe_fn=lambda provider: (False, f'{provider} not ready'),
        sleep_fn=lambda seconds: now.__setitem__('value', now['value'] + seconds),
        time_fn=lambda: now['value'],
        print_fn=outputs.append,
    )

    assert service.warmup_provider('droid', timeout=0.2) is False
    assert 'droid not ready' in outputs
    assert outputs[-1] == '⚠️ Warmup failed: droid'
