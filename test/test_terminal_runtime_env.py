from __future__ import annotations

import terminal_runtime.env as env_module


def test_is_windows_uses_runtime_flags_not_platform_wmi(monkeypatch) -> None:
    monkeypatch.setattr(env_module.os, 'name', 'nt')
    monkeypatch.setattr(env_module.sys, 'platform', 'win32')
    assert env_module.is_windows() is True


def test_is_windows_false_for_non_windows_runtime(monkeypatch) -> None:
    monkeypatch.setattr(env_module.os, 'name', 'posix')
    monkeypatch.setattr(env_module.sys, 'platform', 'linux')
    assert env_module.is_windows() is False
