from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIXES = (
    'askd.adapters',
    'askd.daemon',
    'askd.registry',
)
V2_MAIN_PATH_FILES = (
    'lib/cli/phase2.py',
    'lib/ccbd/app.py',
    'lib/provider_execution/service.py',
    'lib/provider_execution/registry.py',
)
V2_PROVIDER_EXECUTION_FILES = (
    'lib/provider_execution/codex.py',
    'lib/provider_execution/claude.py',
    'lib/provider_execution/gemini.py',
    'lib/provider_execution/opencode.py',
    'lib/provider_execution/droid.py',
)


def _import_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def _called_attributes(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    attrs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attrs.add(node.func.attr)
    return attrs


def test_v2_main_path_does_not_import_standalone_askd_modules() -> None:
    for relative in V2_MAIN_PATH_FILES:
        path = REPO_ROOT / relative
        imports = _import_names(path)
        forbidden = sorted(
            name for name in imports if any(name == prefix or name.startswith(prefix + '.') for prefix in FORBIDDEN_PREFIXES)
        )
        assert forbidden == [], f'{relative} imports standalone askd modules: {forbidden}'


def test_standalone_askd_subsystem_is_not_referenced_by_v2_package_docstrings_only() -> None:
    ccbd_imports = _import_names(REPO_ROOT / 'lib/ccbd/app.py')
    assert 'ccbd.app_runtime' in ccbd_imports
    assert 'ccbd.app_runtime.handlers' in ccbd_imports
    assert 'ccbd.system' in ccbd_imports
    assert 'askd.daemon' not in ccbd_imports
    assert 'askd.handlers.submit' not in ccbd_imports
    assert 'askd.services.dispatcher' not in ccbd_imports
    assert 'askd.registry' not in ccbd_imports


def test_ccbd_runtime_service_modules_do_not_import_askd_service_wrappers() -> None:
    for relative in (
        'lib/ccbd/services/dispatcher.py',
        'lib/ccbd/services/dispatcher_runtime/__init__.py',
        'lib/ccbd/services/runtime.py',
        'lib/ccbd/services/runtime_attach.py',
        'lib/ccbd/services/provider_runtime_facts.py',
    ):
        imports = _import_names(REPO_ROOT / relative)
        forbidden = sorted(
            name
            for name in imports
            if name == 'askd.services.dispatcher' or name == 'askd.services.runtime' or name.startswith('askd.services.runtime.')
        )
        assert forbidden == [], f'{relative} imports askd service wrappers: {forbidden}'


def test_v2_provider_execution_uses_runtime_target_helpers_instead_of_legacy_backend_calls() -> None:
    for relative in V2_PROVIDER_EXECUTION_FILES:
        attrs = _called_attributes(REPO_ROOT / relative)
        assert 'send_text' not in attrs, f'{relative} still calls backend.send_text directly'
        assert 'is_alive' not in attrs, f'{relative} still calls backend.is_alive directly'
