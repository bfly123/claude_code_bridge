from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path


def _load_script_module(name: str, rel_path: str):
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / rel_path
    loader = SourceFileLoader(name, str(script_path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_cask_daemon_request_retries_until_success(tmp_path: Path, monkeypatch) -> None:
    cask = _load_script_module("cask_script_retry", "bin/cask")

    calls = {"count": 0}

    def _try(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            return None
        return ("ok", 0)

    monkeypatch.setattr(cask, "state_file_from_env", lambda _name: None)
    monkeypatch.setattr(cask, "try_daemon_request", _try)
    monkeypatch.setattr(cask, "env_bool", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cask, "find_project_session_file", lambda *_args, **_kwargs: tmp_path / ".codex-session")
    monkeypatch.setattr(cask, "maybe_start_daemon", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cask, "wait_for_daemon_ready", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cask.time, "sleep", lambda _s: None)
    monkeypatch.setenv("CCB_CASKD_RETRY_WAIT_S", "0.01")

    result = cask._daemon_request_with_retries(tmp_path, "hello", 2.0, True, None)
    assert result == ("ok", 0)
    assert calls["count"] >= 3


def test_lask_daemon_request_retries_until_success(tmp_path: Path, monkeypatch) -> None:
    lask = _load_script_module("lask_script_retry", "bin/lask")

    calls = {"count": 0}

    def _try(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            return None
        return ("ok", 0)

    monkeypatch.setattr(lask, "state_file_from_env", lambda _name: None)
    monkeypatch.setattr(lask, "try_daemon_request", _try)
    monkeypatch.setattr(lask, "env_bool", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(lask, "find_project_session_file", lambda *_args, **_kwargs: tmp_path / ".claude-session")
    monkeypatch.setattr(lask, "maybe_start_daemon", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(lask, "wait_for_daemon_ready", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(lask.time, "sleep", lambda _s: None)
    monkeypatch.setenv("CCB_LASKD_RETRY_WAIT_S", "0.01")

    result = lask._daemon_request_with_retries(tmp_path, "hello", 2.0, True, None)
    assert result == ("ok", 0)
    assert calls["count"] >= 3
