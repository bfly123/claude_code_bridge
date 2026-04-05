from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass
class ClaudeHistoryLocator:
    invocation_dir: Path
    project_root: Path
    env: Mapping[str, str]
    home_dir: Path

    def project_dir(self, work_dir: Path) -> Path:
        projects_root = self.home_dir / '.claude' / 'projects'
        candidates: list[Path] = []
        env_pwd = self.env.get('PWD')
        if env_pwd:
            try:
                candidates.append(Path(env_pwd))
            except Exception:
                pass
        candidates.extend([work_dir])
        try:
            candidates.append(work_dir.resolve())
        except Exception:
            pass

        for candidate in candidates:
            project_dir = projects_root / self._project_key(candidate)
            if project_dir.exists():
                return project_dir

        try:
            fallback_path = work_dir.resolve()
        except Exception:
            fallback_path = work_dir
        return projects_root / self._project_key(fallback_path)

    def latest_session_id(self) -> tuple[str | None, bool, Path | None]:
        candidates: list[Path] = []
        for candidate in (self.invocation_dir, self.project_root):
            try:
                path = candidate.resolve()
            except Exception:
                path = candidate.absolute()
            if path not in candidates:
                candidates.append(path)

        session_env_root = self.home_dir / '.claude' / 'session-env'
        best_uuid: Path | None = None
        best_any: Path | None = None
        has_any_history = False
        best_cwd: Path | None = None

        for work_dir in candidates:
            project_dir = self.project_dir(work_dir)
            if not project_dir.exists():
                continue

            session_files = list(project_dir.glob('*.jsonl'))
            if not session_files:
                continue
            has_any_history = True
            try:
                best_in_dir = max(session_files, key=lambda p: p.stat().st_mtime)
                if best_any is None or best_in_dir.stat().st_mtime > best_any.stat().st_mtime:
                    best_any = best_in_dir
                    best_cwd = work_dir
            except Exception:
                pass

            for session_file in session_files:
                try:
                    uuid.UUID(session_file.stem)
                    if session_file.stat().st_size <= 0:
                        continue
                    if not (session_env_root / session_file.stem).exists():
                        continue
                except Exception:
                    continue
                if best_uuid is None:
                    best_uuid = session_file
                    best_cwd = work_dir
                    continue
                try:
                    if session_file.stat().st_mtime > best_uuid.stat().st_mtime:
                        best_uuid = session_file
                        best_cwd = work_dir
                except Exception:
                    continue

        if best_uuid is not None:
            return best_uuid.stem, True, best_cwd
        if has_any_history:
            return None, True, best_cwd
        return None, False, None

    @staticmethod
    def _project_key(work_dir: Path) -> str:
        return re.sub(r'[^A-Za-z0-9]', '-', str(work_dir))
