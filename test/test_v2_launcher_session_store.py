from __future__ import annotations

import json
from pathlib import Path

from launcher.session.claude_store import ClaudeLocalSessionStore
from launcher.session.io import mark_session_inactive, read_session_json


def _normalize(value: str) -> str:
    return str(Path(value).resolve()).replace('\\', '/').lower()


def _store(tmp_path: Path, *, session_name: str = '.claude-session') -> tuple[ClaudeLocalSessionStore, dict]:
    session_path = tmp_path / '.ccb' / session_name
    session_path.parent.mkdir(parents=True, exist_ok=True)
    captured: dict = {'registry': []}

    def _safe_write(path: Path, payload: str) -> tuple[bool, str | None]:
        path.write_text(payload, encoding='utf-8')
        return True, None

    store = ClaudeLocalSessionStore(
        session_path=session_path,
        project_root=tmp_path.resolve(),
        invocation_dir=tmp_path.resolve(),
        ccb_session_id='ai-1',
        project_id='proj-1',
        default_terminal='tmux',
        check_session_writable_fn=lambda path: (True, None, None),
        safe_write_session_fn=_safe_write,
        normalize_path_for_match_fn=_normalize,
        extract_session_work_dir_norm_fn=lambda data: str(data.get('work_dir_norm') or data.get('work_dir') or '').strip(),
        work_dir_match_keys_fn=lambda work_dir: {_normalize(str(work_dir))},
        upsert_registry_fn=lambda payload: captured['registry'].append(payload),
    )
    return store, captured


def test_backfill_work_dir_fields_adds_missing_fields(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    store.session_path.write_text(json.dumps({'active': True}, ensure_ascii=False), encoding='utf-8')

    store.backfill_work_dir_fields()

    data = read_session_json(store.session_path)
    assert data['active'] is True
    assert data['work_dir'] == str(tmp_path.resolve())
    assert data['work_dir_norm'] == _normalize(str(tmp_path.resolve()))


def test_read_local_session_id_rejects_foreign_or_unmarked_session(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    store.session_path.write_text(
        json.dumps({'claude_session_id': '550e8400-e29b-41d4-a716-446655440000'}, ensure_ascii=False),
        encoding='utf-8',
    )
    assert store.read_local_session_id(current_work_dir=tmp_path) is None

    store.session_path.write_text(
        json.dumps(
            {
                'claude_session_id': '550e8400-e29b-41d4-a716-446655440000',
                'work_dir_norm': '/some/other/project',
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    assert store.read_local_session_id(current_work_dir=tmp_path) is None

    store.session_path.write_text(
        json.dumps(
            {
                'session_id': '550e8400-e29b-41d4-a716-446655440000',
                'work_dir_norm': _normalize(str(tmp_path.resolve())),
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    assert store.read_local_session_id(current_work_dir=tmp_path) is None


def test_write_local_session_updates_file_and_registry(tmp_path: Path) -> None:
    store, captured = _store(tmp_path)

    store.write_local_session(
        session_id='550e8400-e29b-41d4-a716-446655440000',
        active=True,
        pane_id='%9',
        pane_title_marker='CCB-Claude',
        terminal='tmux',
    )

    data = read_session_json(store.session_path)
    assert data['claude_session_id'] == '550e8400-e29b-41d4-a716-446655440000'
    assert data['ccb_session_id'] == 'ai-1'
    assert data['ccb_project_id'] == 'proj-1'
    assert data['pane_id'] == '%9'
    assert data['pane_title_marker'] == 'CCB-Claude'
    assert data['terminal'] == 'tmux'
    assert data['work_dir'] == str(tmp_path.resolve())
    assert captured['registry'][0]['providers']['claude']['pane_id'] == '%9'


def test_mark_session_inactive_marks_existing_session(tmp_path: Path) -> None:
    path = tmp_path / '.ccb' / '.codex-session'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'active': True}, ensure_ascii=False), encoding='utf-8')

    def _safe_write(session_path: Path, payload: str) -> tuple[bool, str | None]:
        session_path.write_text(payload, encoding='utf-8')
        return True, None

    mark_session_inactive(path, safe_write_session_fn=_safe_write, ended_at='2026-03-22 12:00:00')

    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['active'] is False
    assert data['ended_at'] == '2026-03-22 12:00:00'
