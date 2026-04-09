from __future__ import annotations

from pathlib import Path
import platform
import shutil
import sys

from cli.management import find_install_dir, get_version_info
from provider_core.registry import CORE_PROVIDER_NAMES, OPTIONAL_PROVIDER_NAMES
from provider_core.runtime_shared import provider_executable


def installation_summary() -> dict[str, object]:
    install_dir = find_install_dir(_script_root())
    info = get_version_info(install_dir)
    return {
        'path': str(install_dir),
        'version': info.get('version'),
        'commit': info.get('commit'),
        'date': info.get('date'),
        'channel': info.get('channel'),
        'platform': info.get('platform'),
        'arch': info.get('arch'),
        'build_time': info.get('build_time'),
        'installed_at': info.get('installed_at'),
        'source_kind': info.get('source_kind'),
        'install_mode': info.get('install_mode'),
    }


def requirements_summary() -> dict[str, object]:
    tmux_path = shutil.which('tmux')
    providers = []
    for provider in tuple(CORE_PROVIDER_NAMES + OPTIONAL_PROVIDER_NAMES):
        executable = provider_executable(provider)
        command_path = shutil.which(executable)
        providers.append(
            {
                'provider': provider,
                'executable': executable,
                'available': command_path is not None,
                'path': command_path,
            }
        )
    return {
        'python_executable': sys.executable,
        'python_version': platform.python_version(),
        'tmux_available': tmux_path is not None,
        'tmux_path': tmux_path,
        'provider_commands': providers,
    }


def _script_root() -> Path:
    return Path(__file__).resolve().parents[4]


__all__ = ['installation_summary', 'requirements_summary']
