from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

try:  # pragma: no branch
    import tomllib as _toml_reader
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    try:
        import tomli as _toml_reader  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover - external fallback
        import toml as _toml_reader  # type: ignore[no-redef]

from agents.models import AgentSpec
from cli.context import CliContext
from cli.models import ParsedStartCommand
from provider_core.contracts import ProviderRuntimeLauncher
from provider_core.pathing import session_filename_for_agent
from provider_core.runtime_shared import provider_start_parts
from provider_profiles import ResolvedProviderProfile, load_resolved_provider_profile, provider_api_env_keys
from workspace.models import WorkspacePlan
from .start_cmd import extract_resume_session_id


def build_runtime_launcher() -> ProviderRuntimeLauncher:
    return ProviderRuntimeLauncher(
        provider='codex',
        launch_mode='codex_tmux',
        prepare_runtime=prepare_runtime,
        build_start_cmd=build_start_cmd,
        build_session_payload=build_session_payload,
        post_launch=post_launch,
    )


def prepare_runtime(runtime_dir: Path) -> dict[str, object]:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    input_fifo = runtime_dir / 'input.fifo'
    output_fifo = runtime_dir / 'output.fifo'
    _ensure_fifo(input_fifo, 0o600)
    _ensure_fifo(output_fifo, 0o644)
    return {
        'input_fifo': input_fifo,
        'output_fifo': output_fifo,
    }


def build_start_cmd(command: ParsedStartCommand, spec: AgentSpec, runtime_dir: Path, launch_session_id: str) -> str:
    profile = load_resolved_provider_profile(runtime_dir)
    codex_home_overrides = _prepare_codex_home_overrides(runtime_dir, profile)
    codex_args = provider_start_parts('codex')
    codex_args.extend(['-c', 'disable_paste_burst=true'])
    if command.auto_permission:
        codex_args.extend(
            [
                '-c',
                'trust_level="trusted"',
                '-c',
                'approval_policy="never"',
                '-c',
                'sandbox_mode="danger-full-access"',
            ]
        )
    codex_args.extend(spec.startup_args)
    if command.restore:
        session_id = _load_resume_session_id(spec, runtime_dir)
        if session_id:
            codex_args.extend(['resume', session_id])

    explicit_env: dict[str, str] = {}
    if profile is not None:
        explicit_env.update(profile.env)
    explicit_env.update(spec.env)

    env_map = {
        'CODEX_RUNTIME_DIR': str(runtime_dir),
        'CODEX_INPUT_FIFO': str(runtime_dir / 'input.fifo'),
        'CODEX_OUTPUT_FIFO': str(runtime_dir / 'output.fifo'),
        'CODEX_TERMINAL': 'tmux',
        'CCB_SESSION_ID': launch_session_id,
        **codex_home_overrides,
        **explicit_env,
    }

    prefix_parts = _build_codex_shell_prefix(profile=profile)
    exports = ' '.join(f'{key}={shlex.quote(str(value))}' for key, value in env_map.items() if str(value).strip())
    if exports:
        prefix_parts.append(f'export {exports}')
    cmd = ' '.join(shlex.quote(str(part)) for part in codex_args)
    if prefix_parts:
        return f"{'; '.join(prefix_parts)}; {cmd}"
    return cmd


def build_session_payload(
    context: CliContext,
    spec: AgentSpec,
    plan: WorkspacePlan,
    runtime_dir: Path,
    run_cwd: Path,
    pane_id: str,
    pane_title_marker: str,
    start_cmd: str,
    launch_session_id: str,
    prepared_state: dict[str, object],
) -> dict[str, object]:
    input_fifo = Path(prepared_state['input_fifo'])
    output_fifo = Path(prepared_state['output_fifo'])
    return {
        'ccb_session_id': launch_session_id,
        'agent_name': spec.name,
        'ccb_project_id': context.project.project_id,
        'runtime_dir': str(runtime_dir),
        'completion_artifact_dir': str(runtime_dir / 'completion'),
        'input_fifo': str(input_fifo),
        'output_fifo': str(output_fifo),
        'terminal': 'tmux',
        'tmux_session': pane_id,
        'pane_id': pane_id,
        'pane_title_marker': pane_title_marker,
        'tmux_log': str(runtime_dir / 'bridge_output.log'),
        'workspace_path': str(plan.workspace_path),
        'work_dir': str(run_cwd),
        'start_dir': str(context.project.project_root),
        'codex_start_cmd': start_cmd,
        'start_cmd': start_cmd,
    }


def post_launch(backend: object, pane_id: str, runtime_dir: Path, launch_session_id: str, prepared_state: dict[str, object]) -> None:
    del launch_session_id
    del prepared_state
    _write_pane_pid(backend, pane_id, runtime_dir / 'codex.pid')
    _spawn_codex_bridge(runtime_dir=runtime_dir, pane_id=pane_id)


def _build_codex_shell_prefix(*, profile: ResolvedProviderProfile | None) -> list[str]:
    if profile is None or profile.inherit_api:
        return []
    return [f'unset {key}' for key in sorted(provider_api_env_keys('codex'))]


def _prepare_codex_home_overrides(runtime_dir: Path, profile: ResolvedProviderProfile | None) -> dict[str, str]:
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
    try:
        if config_path.is_file():
            if getattr(_toml_reader, '__name__', '') == 'toml':
                _toml_reader.loads(config_path.read_text(encoding='utf-8'))
            elif hasattr(_toml_reader, 'load'):
                with config_path.open('rb') as handle:
                    _toml_reader.load(handle)
            else:  # pragma: no cover
                _toml_reader.loads(config_path.read_text(encoding='utf-8'))
        return {}
    except Exception:
        pass

    isolated_home = runtime_dir / 'codex-home'
    isolated_home.mkdir(parents=True, exist_ok=True)
    (isolated_home / 'sessions').mkdir(parents=True, exist_ok=True)
    (isolated_home / 'config.toml').write_text('# isolated by ccb due to invalid source config\n', encoding='utf-8')

    auth_path = source_home / 'auth.json'
    if auth_path.is_file():
        try:
            shutil.copy2(auth_path, isolated_home / 'auth.json')
        except Exception:
            pass

    return {
        'CODEX_HOME': str(isolated_home),
        'CODEX_SESSION_ROOT': str(isolated_home / 'sessions'),
    }


def _load_resume_session_id(spec: AgentSpec, runtime_dir: Path) -> str | None:
    session_path = _agent_session_path(spec, runtime_dir)
    if session_path is None or not session_path.is_file():
        session_path = _default_session_path(runtime_dir)
    if session_path is None or not session_path.is_file():
        return None
    try:
        data = json.loads(session_path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    session_id = str(data.get('codex_session_id') or '').strip()
    if session_id:
        return session_id
    start_cmd = str(data.get('codex_start_cmd') or data.get('start_cmd') or '').strip()
    if not start_cmd:
        return None
    return extract_resume_session_id(start_cmd)


def _agent_session_path(spec: AgentSpec, runtime_dir: Path) -> Path | None:
    ccb_dir = _find_project_ccb_dir(runtime_dir)
    if ccb_dir is None:
        return None
    return ccb_dir / session_filename_for_agent('codex', spec.name)


def _default_session_path(runtime_dir: Path) -> Path | None:
    ccb_dir = _find_project_ccb_dir(runtime_dir)
    if ccb_dir is None:
        return None
    return ccb_dir / session_filename_for_agent('codex', 'codex')


def _find_project_ccb_dir(runtime_dir: Path) -> Path | None:
    current = Path(runtime_dir)
    for parent in (current, *current.parents):
        if parent.name == '.ccb':
            return parent
    return None


def _spawn_codex_bridge(*, runtime_dir: Path, pane_id: str) -> None:
    bridge_script = Path(__file__).with_name('bridge.py')
    env = os.environ.copy()
    env['CODEX_TERMINAL'] = 'tmux'
    env['CODEX_TMUX_SESSION'] = pane_id
    env['CODEX_RUNTIME_DIR'] = str(runtime_dir)
    env['CODEX_INPUT_FIFO'] = str(runtime_dir / 'input.fifo')
    env['CODEX_OUTPUT_FIFO'] = str(runtime_dir / 'output.fifo')
    env['CODEX_TMUX_LOG'] = str(runtime_dir / 'bridge_output.log')
    env.update(_bridge_runtime_env(runtime_dir))
    existing_pythonpath = env.get('PYTHONPATH', '')
    lib_root = str(Path(__file__).resolve().parents[2].parent)
    env['PYTHONPATH'] = lib_root if not existing_pythonpath else lib_root + os.pathsep + existing_pythonpath
    proc = subprocess.Popen(
        [sys.executable, str(bridge_script), '--runtime-dir', str(runtime_dir)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    (runtime_dir / 'bridge.pid').write_text(f'{proc.pid}\n', encoding='utf-8')


def _bridge_runtime_env(runtime_dir: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    session_file = _session_file_for_runtime_dir(runtime_dir)
    if session_file is not None:
        env['CCB_SESSION_FILE'] = str(session_file)
    profile = load_resolved_provider_profile(runtime_dir)
    env.update(_prepare_codex_home_overrides(runtime_dir, profile))
    return env


def _session_file_for_runtime_dir(runtime_dir: Path) -> Path | None:
    ccb_dir = _find_project_ccb_dir(runtime_dir)
    if ccb_dir is None:
        return None
    try:
        agent_name = runtime_dir.parents[1].name
    except Exception:
        return None
    agent_name = str(agent_name or '').strip()
    if not agent_name:
        return None
    return ccb_dir / session_filename_for_agent('codex', agent_name)


def _write_pane_pid(backend: object, pane_id: str, path: Path) -> None:
    try:
        result = backend._tmux_run(  # type: ignore[attr-defined]
            ['display-message', '-p', '-t', pane_id, '#{pane_pid}'],
            capture=True,
            timeout=1.0,
        )
    except Exception:
        return
    pane_pid = (result.stdout or '').strip()
    if pane_pid.isdigit():
        path.write_text(f'{pane_pid}\n', encoding='utf-8')


def _ensure_fifo(path: Path, mode: int) -> None:
    if path.exists():
        return
    os.mkfifo(path, mode)


__all__ = ['build_runtime_launcher', 'build_start_cmd']
