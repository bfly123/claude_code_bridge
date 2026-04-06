from __future__ import annotations

import os
from pathlib import Path
import shutil

try:  # pragma: no branch
    import tomllib as _toml_reader
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    try:
        import tomli as _toml_reader  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover - external fallback
        import toml as _toml_reader  # type: ignore[no-redef]


def prepare_codex_home_overrides(runtime_dir: Path, profile) -> dict[str, str]:
    if profile is not None and profile.runtime_home:
        runtime_home = Path(profile.runtime_home).expanduser()
        runtime_home.mkdir(parents=True, exist_ok=True)
        (runtime_home / 'sessions').mkdir(parents=True, exist_ok=True)
        return {
            'CODEX_HOME': str(runtime_home),
            'CODEX_SESSION_ROOT': str(runtime_home / 'sessions'),
        }
    source_home = Path(os.environ.get('CODEX_HOME') or (Path.home() / '.codex')).expanduser()
    config_path = source_home / 'config.toml'
    if _source_config_valid(config_path):
        return {}
    isolated_home = runtime_dir / 'codex-home'
    isolated_home.mkdir(parents=True, exist_ok=True)
    (isolated_home / 'sessions').mkdir(parents=True, exist_ok=True)
    (isolated_home / 'config.toml').write_text('# isolated by ccb due to invalid source config\n', encoding='utf-8')
    _copy_auth_file(source_home / 'auth.json', isolated_home / 'auth.json')
    return {
        'CODEX_HOME': str(isolated_home),
        'CODEX_SESSION_ROOT': str(isolated_home / 'sessions'),
    }


def _source_config_valid(config_path: Path) -> bool:
    try:
        if config_path.is_file():
            if getattr(_toml_reader, '__name__', '') == 'toml':
                _toml_reader.loads(config_path.read_text(encoding='utf-8'))
            elif hasattr(_toml_reader, 'load'):
                with config_path.open('rb') as handle:
                    _toml_reader.load(handle)
            else:  # pragma: no cover
                _toml_reader.loads(config_path.read_text(encoding='utf-8'))
        return True
    except Exception:
        return False


def _copy_auth_file(source: Path, target: Path) -> None:
    if not source.is_file():
        return
    try:
        shutil.copy2(source, target)
    except Exception:
        pass


__all__ = ['prepare_codex_home_overrides']
