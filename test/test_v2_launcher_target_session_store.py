from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from launcher.session.io import read_session_json
from launcher.session.target_store import LauncherTargetSessionStore


def _normalize(value: str) -> str:
    return str(Path(value).resolve()).replace("\\", "/").lower()


def _store(tmp_path: Path) -> tuple[LauncherTargetSessionStore, dict]:
    project_root = (tmp_path / "repo").resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    ccb_dir = project_root / ".ccb"
    ccb_dir.mkdir(parents=True, exist_ok=True)
    captured: dict = {"registry": [], "cleared": 0}

    def _safe_write(path: Path, payload: str) -> tuple[bool, str | None]:
        path.write_text(payload, encoding="utf-8")
        return True, None

    store = LauncherTargetSessionStore(
        project_root=project_root,
        invocation_dir=project_root,
        ccb_session_id="ai-1",
        terminal_type="tmux",
        project_session_path_fn=lambda name: ccb_dir / name,
        compute_project_id_fn=lambda path: f"proj:{path.name}",
        normalize_path_for_match_fn=_normalize,
        check_session_writable_fn=lambda path: (True, None, None),
        safe_write_session_fn=_safe_write,
        read_session_json_fn=read_session_json,
        upsert_registry_fn=lambda payload: captured["registry"].append(payload) or True,
        clear_codex_log_binding_fn=lambda data: captured.__setitem__("cleared", captured["cleared"] + 1) or {
            key: value for key, value in data.items() if key != "tmux_log"
        },
    )
    return store, captured


def test_write_codex_session_rewrites_runtime_fields_and_registry(tmp_path: Path) -> None:
    store, captured = _store(tmp_path)
    session_path = store.project_session_path_fn(".codex-session")
    session_path.write_text(
        json.dumps({"tmux_log": "/old/log", "codex_session_id": "sess-1"}, ensure_ascii=False),
        encoding="utf-8",
    )
    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)

    ok = store.write_codex_session(
        runtime,
        "tmux-main",
        runtime / "in.fifo",
        runtime / "out.fifo",
        pane_id="%3",
        pane_title_marker="CCB-Codex",
        codex_start_cmd="codex --model gpt-5",
        resume=False,
    )

    assert ok is True
    data = read_session_json(session_path)
    assert data["ccb_session_id"] == "ai-1"
    assert data["runtime_dir"] == str(runtime)
    assert data["tmux_log"] == str(runtime / "bridge_output.log")
    assert data["start_cmd"] == "codex --model gpt-5"
    assert data["work_dir"] == str(store.project_root)
    assert data["work_dir_norm"] == _normalize(str(store.project_root))
    assert captured["cleared"] == 1
    assert captured["registry"][0]["providers"]["codex"]["pane_id"] == "%3"


def test_write_simple_target_session_adds_ccb_session_id_for_opencode(tmp_path: Path) -> None:
    store, captured = _store(tmp_path)
    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)

    ok = store.write_simple_target_session(
        "opencode",
        runtime,
        "tmux-main",
        pane_id="%5",
        pane_title_marker="CCB-OpenCode",
        start_cmd="opencode run",
    )

    assert ok is True
    data = read_session_json(store.project_session_path_fn(".opencode-session"))
    assert data["ccb_session_id"] == "ai-1"
    assert data["start_cmd"] == "opencode run"
    assert captured["registry"][0]["providers"]["opencode"]["session_file"].endswith(".opencode-session")


def test_write_droid_session_captures_droid_metadata(tmp_path: Path, monkeypatch) -> None:
    store, captured = _store(tmp_path)
    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    droid_log = tmp_path / "droid" / "session.log"
    droid_log.parent.mkdir(parents=True, exist_ok=True)
    droid_log.write_text("stub", encoding="utf-8")

    class _Reader:
        def __init__(self, work_dir: Path) -> None:
            self.work_dir = work_dir

        def current_session_path(self) -> Path:
            return droid_log

    stub = types.ModuleType("droid_comm")
    stub.DroidLogReader = _Reader
    stub.read_droid_session_start = lambda path: (str(store.project_root), "droid-sess-1")
    monkeypatch.setitem(sys.modules, "droid_comm", stub)

    ok = store.write_droid_session(
        runtime,
        "tmux-main",
        pane_id="%7",
        pane_title_marker="CCB-Droid",
        start_cmd="droid --continue",
    )

    assert ok is True
    data = read_session_json(store.project_session_path_fn(".droid-session"))
    assert data["droid_session_id"] == "droid-sess-1"
    assert data["droid_session_path"] == str(droid_log)
    assert captured["registry"][0]["providers"]["droid"]["droid_session_id"] == "droid-sess-1"


def test_write_cend_registry_writes_dual_provider_mapping(tmp_path: Path) -> None:
    store, captured = _store(tmp_path)

    ok = store.write_cend_registry(claude_pane_id="%1", codex_pane_id="%2")

    assert ok is True
    payload = captured["registry"][0]
    assert payload["providers"]["claude"]["pane_id"] == "%1"
    assert payload["providers"]["codex"]["pane_id"] == "%2"
    assert payload["ccb_project_id"] == "proj:repo"
    assert "claude_pane_id" not in payload
    assert "codex_pane_id" not in payload
