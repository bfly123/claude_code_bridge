from __future__ import annotations

from types import SimpleNamespace

import terminal_runtime.backend_env as backend_env


def test_get_backend_env_prefers_explicit_env(monkeypatch) -> None:
    monkeypatch.setenv("CCB_BACKEND_ENV", "wsl")
    monkeypatch.setattr(backend_env.sys, "platform", "linux")

    assert backend_env.get_backend_env() == "wsl"


def test_apply_backend_env_uses_existing_wsl_paths(monkeypatch) -> None:
    monkeypatch.setattr(backend_env.sys, "platform", "win32")
    monkeypatch.setenv("CCB_BACKEND_ENV", "wsl")
    monkeypatch.delenv("CODEX_SESSION_ROOT", raising=False)
    monkeypatch.delenv("GEMINI_ROOT", raising=False)
    monkeypatch.setattr(
        backend_env,
        "_wsl_probe_distro_and_home",
        lambda: ("Ubuntu", "/home/demo"),
    )
    monkeypatch.setattr(
        backend_env.Path,
        "exists",
        lambda self: str(self).endswith(r"\\.codex\\sessions"),
    )

    backend_env.apply_backend_env()

    assert backend_env.os.environ["CODEX_SESSION_ROOT"].endswith(r".codex\sessions")
    assert backend_env.os.environ["GEMINI_ROOT"].endswith(r".gemini\tmp")


def test_apply_backend_env_falls_back_to_localhost_prefix(monkeypatch) -> None:
    monkeypatch.setattr(backend_env.sys, "platform", "win32")
    monkeypatch.setenv("CCB_BACKEND_ENV", "wsl")
    monkeypatch.delenv("CODEX_SESSION_ROOT", raising=False)
    monkeypatch.delenv("GEMINI_ROOT", raising=False)
    monkeypatch.setattr(
        backend_env,
        "_wsl_probe_distro_and_home",
        lambda: ("Ubuntu", "/root"),
    )
    monkeypatch.setattr(backend_env.Path, "exists", lambda self: False)

    backend_env.apply_backend_env()

    assert backend_env.os.environ["CODEX_SESSION_ROOT"].startswith(r"\\wsl.localhost\Ubuntu")
    assert backend_env.os.environ["GEMINI_ROOT"].startswith(r"\\wsl.localhost\Ubuntu")
