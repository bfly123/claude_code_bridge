from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from launcher.session.io import read_session_json
from launcher.session.payloads import build_claude_registry_payload


@dataclass
class ClaudeLocalSessionStore:
    session_path: Path
    project_root: Path
    invocation_dir: Path
    ccb_session_id: str
    project_id: str | None
    default_terminal: str | None
    check_session_writable_fn: Callable[[Path], tuple[bool, str | None, str | None]]
    safe_write_session_fn: Callable[[Path, str], tuple[bool, str | None]]
    normalize_path_for_match_fn: Callable[[str], str]
    extract_session_work_dir_norm_fn: Callable[[dict], str]
    work_dir_match_keys_fn: Callable[[Path], set[str]]
    upsert_registry_fn: Callable[[dict], object]

    def backfill_work_dir_fields(self) -> None:
        path = self.session_path
        if not path.exists():
            return
        data = read_session_json(path)
        if not isinstance(data, dict) or not data:
            return
        changed = False
        work_dir = str(self.project_root)
        work_dir_norm = self.normalize_path_for_match_fn(work_dir)
        if not str(data.get("work_dir") or "").strip():
            data["work_dir"] = work_dir
            changed = True
        if not str(data.get("work_dir_norm") or "").strip():
            data["work_dir_norm"] = work_dir_norm
            changed = True
        if not changed:
            return
        self.safe_write_session_fn(path, json.dumps(data, ensure_ascii=False, indent=2))

    def read_local_session_id(self, *, current_work_dir: Path) -> str | None:
        data = read_session_json(self.session_path)
        sid = data.get("claude_session_id")
        if isinstance(sid, str) and sid.strip():
            recorded_norm = self.extract_session_work_dir_norm_fn(data)
            if not recorded_norm:
                return None
            current_keys = self.work_dir_match_keys_fn(current_work_dir)
            if current_keys and recorded_norm not in current_keys:
                return None
            return sid.strip()
        return None

    def write_local_session(
        self,
        session_id: str | None = None,
        *,
        active: bool = True,
        pane_id: str | None = None,
        pane_title_marker: str | None = None,
        terminal: str | None = None,
    ) -> None:
        path = self.session_path
        writable, reason, fix = self.check_session_writable_fn(path)
        if not writable:
            print(f"❌ Cannot write {path.name}: {reason}", file=sys.stderr)
            print(f"💡 Fix: {fix}", file=sys.stderr)
            return

        data = read_session_json(path) if path.exists() else {}
        work_dir = self.project_root
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        if session_id:
            data["claude_session_id"] = session_id
        data["ccb_session_id"] = self.ccb_session_id
        if self.project_id:
            data["ccb_project_id"] = self.project_id
        else:
            data["ccb_project_id"] = data.get("ccb_project_id")
        data["work_dir"] = str(work_dir)
        data["work_dir_norm"] = self.normalize_path_for_match_fn(str(work_dir))
        data["start_dir"] = str(self.invocation_dir)
        data["terminal"] = terminal or self.default_terminal
        data["active"] = bool(active)
        data["started_at"] = data.get("started_at") or now
        data["updated_at"] = now
        if pane_id:
            data["pane_id"] = pane_id
        if pane_title_marker:
            data["pane_title_marker"] = pane_title_marker

        ok, err = self.safe_write_session_fn(path, json.dumps(data, ensure_ascii=False, indent=2))
        if not ok:
            if err:
                print(err, file=sys.stderr)
            return
        if pane_id:
            try:
                self.upsert_registry_fn(
                    build_claude_registry_payload(
                        ccb_session_id=self.ccb_session_id,
                        project_id=self.project_id,
                        project_root=self.project_root,
                        terminal=terminal or self.default_terminal,
                        path=path,
                        pane_id=pane_id,
                        pane_title_marker=pane_title_marker,
                        data=data,
                    )
                )
            except Exception:
                pass
