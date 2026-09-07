import importlib.util
import json
from pathlib import Path

import pytest


def test_failed_cleanup_preserves_original_error_and_residue(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / 'scripts/single_lane_multi_workgroup_smoke.py'
    spec = importlib.util.spec_from_file_location('smoke_cleanup_report', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, '_smoke_env', lambda **kwargs: {})

    def fail_prepare(root):
        raise RuntimeError('original failure')

    def fail_cleanup(*args, **kwargs):
        raise RuntimeError('CLI unavailable')

    monkeypatch.setattr(module, '_prepare_repository', fail_prepare)
    monkeypatch.setattr(module, '_run_logged', fail_cleanup)
    residue = {'owned_processes': [{'pid': 123}], 'socket_entries': []}
    monkeypatch.setattr(module, '_post_cleanup_evidence', lambda root: residue)
    root = tmp_path / 'smoke'
    with pytest.raises(RuntimeError, match='original failure'):
        module.run_smoke(project_root=root, count=1, shape='parallel', ccb_test=script)
    report = json.loads((root / '.ccb/evidence/g5-fake-fullflow/report.json').read_text())
    assert report['error'] == 'original failure'
    assert report['cleanup_error'] == 'CLI unavailable'
    assert report['post_cleanup'] == residue
