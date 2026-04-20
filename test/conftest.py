from __future__ import annotations

import sys
from pathlib import Path

import pytest

repo_root = Path(__file__).resolve().parents[1]
lib_dir = repo_root / "lib"
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

import project.resolver as project_resolver_module


def pytest_configure() -> None:
    if str(lib_dir) not in sys.path:
        sys.path.insert(0, str(lib_dir))


@pytest.fixture(autouse=True)
def _ignore_host_level_tmp_anchor(monkeypatch, tmp_path_factory) -> None:
    original = project_resolver_module.find_parent_project_anchor_dir
    pytest_tmp_root = tmp_path_factory.getbasetemp().resolve()

    def _patched(path: Path):
        result = original(path)
        if result is None:
            return None
        anchor_root = result.parent.resolve()
        if pytest_tmp_root.is_relative_to(anchor_root) and not anchor_root.is_relative_to(pytest_tmp_root):
            return None
        return result

    monkeypatch.setattr(project_resolver_module, 'find_parent_project_anchor_dir', _patched)
