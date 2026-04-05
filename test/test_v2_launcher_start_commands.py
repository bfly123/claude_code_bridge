from __future__ import annotations

import hashlib
import json
from pathlib import Path

from launcher.commands.factory import LauncherStartCommandFactory
from launcher.session.io import read_session_json


def _normalize(value: str) -> str:
    return str(Path(value).resolve()).replace('\\', '/').lower()


def _factory(tmp_path: Path, *, resume: bool = False, auto: bool = False) -> LauncherStartCommandFactory:
    project_root = tmp_path / 'repo'
    project_root.mkdir(parents=True, exist_ok=True)
    ccb_dir = project_root / '.ccb'
    ccb_dir.mkdir(parents=True, exist_ok=True)
    return LauncherStartCommandFactory(
        project_root=project_root.resolve(),
        invocation_dir=project_root.resolve(),
        resume=resume,
        auto=auto,
        project_session_path_fn=lambda name: ccb_dir / name,
        normalize_path_for_match_fn=_normalize,
        normpath_within_fn=lambda child, parent: child == parent or child.startswith(parent.rstrip('/') + '/'),
        build_cd_cmd_fn=lambda path: f'cd {path} && ',
        translate_fn=lambda key, **kwargs: f'{key}:{kwargs.get("provider", "")}',
    )


def test_codex_resume_updates_local_session_file(monkeypatch, tmp_path: Path) -> None:
    factory = _factory(tmp_path, resume=True)
    session_root = tmp_path / 'codex-sessions'
    log_path = session_root / '2026' / '03' / 'latest.jsonl'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    subdir = factory.project_root / 'subdir'
    subdir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(
            {
                'type': 'session_meta',
                'payload': {
                    'cwd': str(subdir),
                    'id': 'abc12345-6789-0000-0000-000000000000',
                },
            }
        )
        + '\n',
        encoding='utf-8',
    )
    monkeypatch.setenv('CODEX_SESSION_ROOT', str(session_root))

    cmd = factory.build_codex_start_cmd()

    assert cmd.endswith('resume abc12345-6789-0000-0000-000000000000')
    data = read_session_json(factory.project_session_path_fn('.codex-session'))
    assert data['codex_session_id'] == 'abc12345-6789-0000-0000-000000000000'
    assert data['work_dir'] == str(factory.project_root)


def test_gemini_resume_uses_latest_hash(monkeypatch, tmp_path: Path) -> None:
    factory = _factory(tmp_path, resume=True)
    gemini_root = tmp_path / 'gemini-root'
    project_hash = hashlib.sha256(str(factory.project_root).encode()).hexdigest()
    chats = gemini_root / project_hash / 'chats'
    chats.mkdir(parents=True, exist_ok=True)
    (chats / 'session-1.json').write_text('{}', encoding='utf-8')
    monkeypatch.setenv('GEMINI_ROOT', str(gemini_root))

    cmd = factory.build_gemini_start_cmd()

    assert cmd == f'cd {factory.project_root} && gemini --resume latest'


def test_opencode_auto_config_writes_permissions(tmp_path: Path, monkeypatch) -> None:
    factory = _factory(tmp_path, auto=True)
    monkeypatch.chdir(factory.project_root)

    factory.ensure_opencode_auto_config()

    config = json.loads((factory.project_root / 'opencode.json').read_text(encoding='utf-8'))
    assert config['permission']['edit'] == 'allow'
    assert config['permission']['webfetch'] == 'allow'


def test_droid_build_cmd_prefers_resume_cmd(monkeypatch, tmp_path: Path) -> None:
    factory = _factory(tmp_path, resume=True)
    monkeypatch.setenv('DROID_RESUME_CMD', 'droid-resume-custom')
    factory.get_latest_droid_session_id = lambda: ('sess-12345678', True, factory.project_root)  # type: ignore[method-assign]

    cmd = factory.build_droid_start_cmd()

    assert cmd == 'droid-resume-custom'


def test_get_start_cmd_dispatches_to_provider_builders(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    factory.build_codex_start_cmd = lambda: 'codex-cmd'  # type: ignore[method-assign]
    factory.build_gemini_start_cmd = lambda: 'gemini-cmd'  # type: ignore[method-assign]
    factory.build_opencode_start_cmd = lambda: 'opencode-cmd'  # type: ignore[method-assign]
    factory.build_droid_start_cmd = lambda: 'droid-cmd'  # type: ignore[method-assign]

    assert factory.get_start_cmd('codex') == 'codex-cmd'
    assert factory.get_start_cmd('gemini') == 'gemini-cmd'
    assert factory.get_start_cmd('opencode') == 'opencode-cmd'
    assert factory.get_start_cmd('droid') == 'droid-cmd'
    assert factory.get_start_cmd('unknown') == ''
