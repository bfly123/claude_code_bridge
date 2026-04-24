from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from ..session_paths import read_session_payload, session_file_for_runtime_dir, state_dir_for_runtime_dir


_ENV_ASSIGNMENT_RE = re.compile(
    r"(?:(?:^|[;\s])export\s+|(?:^|[;\s]))(?P<name>[A-Z0-9_]+)=(?P<value>'[^']*'|\"[^\"]*\"|[^;\s]+)"
)


@dataclass(frozen=True)
class CodexHomeLayout:
    codex_home: Path
    session_root: Path


def resolve_codex_home_layout(runtime_dir: Path, profile) -> CodexHomeLayout:
    explicit_runtime_home = _profile_runtime_home(profile)
    if explicit_runtime_home is not None:
        return CodexHomeLayout(
            codex_home=explicit_runtime_home,
            session_root=explicit_runtime_home / 'sessions',
        )

    existing = _existing_layout(runtime_dir)
    if existing is not None:
        return existing

    isolated_home = _managed_isolated_home(runtime_dir)
    return CodexHomeLayout(
        codex_home=isolated_home,
        session_root=isolated_home / 'sessions',
    )


def prepare_codex_home_overrides(runtime_dir: Path, profile) -> dict[str, str]:
    layout = resolve_codex_home_layout(runtime_dir, profile)
    layout.codex_home.mkdir(parents=True, exist_ok=True)
    layout.session_root.mkdir(parents=True, exist_ok=True)
    _prepare_managed_home(_system_codex_home(), layout.codex_home)

    return {
        'CODEX_HOME': str(layout.codex_home),
        'CODEX_SESSION_ROOT': str(layout.session_root),
    }


def _profile_runtime_home(profile) -> Path | None:
    runtime_home = getattr(profile, 'runtime_home', None) if profile is not None else None
    if not runtime_home:
        return None
    return Path(runtime_home).expanduser()


def _existing_layout(runtime_dir: Path) -> CodexHomeLayout | None:
    session_file = session_file_for_runtime_dir(runtime_dir)
    if session_file is None or not session_file.is_file():
        return None
    data = read_session_payload(session_file)
    if not isinstance(data, dict):
        return None
    return _layout_from_payload(data)


def _layout_from_payload(data: dict[str, object]) -> CodexHomeLayout | None:
    codex_home = _path_or_none(data.get('codex_home'))
    session_root = _path_or_none(data.get('codex_session_root'))
    if session_root is None:
        session_root = _session_root_from_commands(data)
    if session_root is None and codex_home is not None:
        session_root = codex_home / 'sessions'
    if session_root is None:
        session_root = _session_root_from_log_path(data.get('codex_session_path'))
    if session_root is None:
        return None
    if codex_home is None:
        codex_home = _codex_home_from_commands(data)
    if codex_home is None:
        codex_home = _legacy_root_to_home(session_root)
    _migrate_legacy_session_root(session_root, codex_home / 'sessions')
    return CodexHomeLayout(codex_home=codex_home, session_root=codex_home / 'sessions')


def _session_root_from_commands(data: dict[str, object]) -> Path | None:
    commands = (
        str(data.get('codex_start_cmd') or '').strip(),
        str(data.get('start_cmd') or '').strip(),
    )
    for command in commands:
        session_root = _extract_command_path(command, 'CODEX_SESSION_ROOT')
        if session_root is not None:
            return session_root
        codex_home = _extract_command_path(command, 'CODEX_HOME')
        if codex_home is not None:
            return codex_home / 'sessions'
    return None


def _codex_home_from_commands(data: dict[str, object]) -> Path | None:
    commands = (
        str(data.get('codex_start_cmd') or '').strip(),
        str(data.get('start_cmd') or '').strip(),
    )
    for command in commands:
        codex_home = _extract_command_path(command, 'CODEX_HOME')
        if codex_home is not None:
            return codex_home
    return None


def _extract_command_path(command: str, env_name: str) -> Path | None:
    if not command:
        return None
    for match in _ENV_ASSIGNMENT_RE.finditer(command):
        if match.group('name') != env_name:
            continue
        return _path_or_none(_unquote_env_value(match.group('value')))
    return None


def _unquote_env_value(value: str) -> str:
    text = str(value or '').strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    return text


def _session_root_from_log_path(value: object) -> Path | None:
    log_path = _path_or_none(value)
    if log_path is None:
        return None
    for parent in (log_path.parent, *log_path.parents):
        if parent.name == 'sessions':
            return parent
    return None


def _path_or_none(value: object) -> Path | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser()
    except Exception:
        return None


def _managed_state_dir(runtime_dir: Path) -> Path:
    derived = state_dir_for_runtime_dir(runtime_dir)
    if derived is not None:
        return derived
    return Path(runtime_dir).expanduser() / 'codex-state'


def _managed_isolated_home(runtime_dir: Path) -> Path:
    return _managed_state_dir(runtime_dir) / 'home'
def _legacy_root_to_home(session_root: Path) -> Path:
    normalized_root = Path(session_root).expanduser()
    if normalized_root.name == 'sessions':
        parent = normalized_root.parent
        if parent.name == 'home':
            return parent
        return parent / 'home'
    return normalized_root / 'home'


def _migrate_legacy_session_root(source_root: Path, target_root: Path) -> None:
    normalized_source = Path(source_root).expanduser()
    normalized_target = Path(target_root).expanduser()
    if normalized_source == normalized_target:
        normalized_target.mkdir(parents=True, exist_ok=True)
        return
    if normalized_source.name != 'sessions':
        normalized_target.mkdir(parents=True, exist_ok=True)
        return
    if normalized_target.exists():
        return
    normalized_target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(normalized_source), str(normalized_target))
    except Exception:
        normalized_target.mkdir(parents=True, exist_ok=True)


def _system_codex_home() -> Path:
    return Path(os.environ.get('CODEX_HOME') or (Path.home() / '.codex')).expanduser()


def _prepare_managed_home(source_home: Path, target_home: Path) -> None:
    target_home.mkdir(parents=True, exist_ok=True)
    (target_home / 'sessions').mkdir(parents=True, exist_ok=True)
    target_config = target_home / 'config.toml'
    if _source_config_valid(source_home / 'config.toml'):
        _sync_file(source_home / 'config.toml', target_config)
    elif not target_config.exists():
        target_config.write_text('# ccb agent-local codex config\n', encoding='utf-8')
    _sync_auth_file(source_home / 'auth.json', target_home / 'auth.json')
    _sync_tree(source_home / 'skills', target_home / 'skills')
    _sync_tree(source_home / 'commands', target_home / 'commands')


def _import_optional_toml_reader():
    for module_name in ('tomllib', 'tomli', 'toml'):
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
    return None


def _source_config_valid(config_path: Path) -> bool:
    try:
        if not config_path.is_file():
            return True
        reader = _import_optional_toml_reader()
        if reader is None:
            # Old/system Python may lack a TOML parser. Validation here is only a best-effort
            # safety check; absence of the validator must not block daemon startup or config sync.
            return True
        if getattr(reader, '__name__', '') == 'toml':
            reader.loads(config_path.read_text(encoding='utf-8'))
        elif hasattr(reader, 'load'):
            with config_path.open('rb') as handle:
                reader.load(handle)
        elif hasattr(reader, 'loads'):  # pragma: no cover - defensive fallback
            reader.loads(config_path.read_text(encoding='utf-8'))
        else:  # pragma: no cover - unsupported parser shim
            return True
        return True
    except Exception:
        return False


def _sync_auth_file(source: Path, target: Path) -> None:
    if not source.is_file():
        return
    try:
        shutil.copy2(source, target)
    except Exception:
        pass


def _sync_file(source: Path, target: Path) -> None:
    if not source.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, target)
    except Exception:
        pass


def _sync_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(source, target, dirs_exist_ok=True)
    except Exception:
        pass


__all__ = ['CodexHomeLayout', 'prepare_codex_home_overrides', 'resolve_codex_home_layout']
