from __future__ import annotations

from pathlib import Path

import askd_client
from providers import GASK_CLIENT_SPEC


def test_maybe_start_daemon_uses_target_work_dir(monkeypatch, tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    cfg_dir = project_dir / ".ccb"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / ".gemini-session").write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    def _fake_popen(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        class _P:
            pass
        return _P()

    monkeypatch.setattr(askd_client, "find_project_session_file", lambda wd, name: cfg_dir / ".gemini-session")
    monkeypatch.setattr(askd_client.shutil, "which", lambda _: None)
    monkeypatch.setattr(askd_client.subprocess, "Popen", _fake_popen)

    ok = askd_client.maybe_start_daemon(GASK_CLIENT_SPEC, project_dir)
    assert ok is True

    kwargs = captured.get("kwargs")
    assert isinstance(kwargs, dict)
    assert kwargs.get("cwd") == str(project_dir)
    env = kwargs.get("env")
    assert isinstance(env, dict)
    assert env.get("CCB_WORK_DIR") == str(project_dir)
