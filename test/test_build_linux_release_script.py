from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "build_linux_release.py"
    spec = importlib.util.spec_from_file_location("build_linux_release", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_normalize_arch_maps_common_aliases() -> None:
    module = _load_module()

    assert module.normalize_arch("amd64") == "x86_64"
    assert module.normalize_arch("x86_64") == "x86_64"
    assert module.normalize_arch("arm64") == "aarch64"
    assert module.normalize_arch("aarch64") == "aarch64"


def test_copy_repo_tree_excludes_runtime_state(tmp_path: Path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    destination = tmp_path / "out"
    (repo_root / ".git").mkdir(parents=True)
    (repo_root / ".ccb" / "ccbd").mkdir(parents=True)
    (repo_root / "lib").mkdir(parents=True)
    (repo_root / "ccb").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (repo_root / "install.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (repo_root / "lib" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (repo_root / ".ccb" / "ccbd" / "lease.json").write_text("{}", encoding="utf-8")

    module.copy_repo_tree(repo_root, destination)

    assert (destination / "lib" / "app.py").exists()
    assert not (destination / ".git").exists()
    assert not (destination / ".ccb").exists()


def test_dirty_worktree_entries_reads_porcelain_output(monkeypatch) -> None:
    module = _load_module()

    def _fake_run(cmd, **kwargs):
        assert cmd[-2:] == ["--porcelain", "--untracked-files=all"]
        return SimpleNamespace(returncode=0, stdout=" M install.sh\n?? scripts/build_linux_release.py\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    entries = module.dirty_worktree_entries(Path("/tmp/repo"))

    assert entries == (" M install.sh", "?? scripts/build_linux_release.py")


def test_ensure_clean_worktree_raises_on_dirty(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "dirty_worktree_entries",
        lambda repo_root: (" M install.sh", "?? scripts/build_linux_release.py"),
    )

    try:
        module.ensure_clean_worktree(Path("/tmp/repo"))
    except RuntimeError as exc:
        text = str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    assert "dirty worktree" in text
    assert "install.sh" in text


def test_export_release_tree_uses_git_archive_when_clean(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    destination = tmp_path / "out"
    repo_root.mkdir()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(module, "is_git_checkout", lambda path: True)
    monkeypatch.setattr(module, "ensure_clean_worktree", lambda path: calls.append(("clean", path)))
    monkeypatch.setattr(
        module,
        "export_git_archive",
        lambda path, dest, *, git_ref: calls.append(("archive", path, dest, git_ref)),
    )
    monkeypatch.setattr(module, "copy_repo_tree", lambda path, dest: calls.append(("copy", path, dest)))

    module.export_release_tree(repo_root, destination, git_ref="HEAD", allow_dirty=False)

    assert calls == [
        ("clean", repo_root),
        ("archive", repo_root, destination, "HEAD"),
    ]


def test_export_release_tree_allows_dirty_preview(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    destination = tmp_path / "out"
    repo_root.mkdir()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(module, "is_git_checkout", lambda path: True)
    monkeypatch.setattr(
        module,
        "copy_repo_tree",
        lambda path, dest: calls.append(("copy", path, dest)),
    )
    monkeypatch.setattr(module, "ensure_clean_worktree", lambda path: calls.append(("clean", path)))
    monkeypatch.setattr(
        module,
        "export_git_archive",
        lambda path, dest, *, git_ref: calls.append(("archive", path, dest, git_ref)),
    )

    module.export_release_tree(repo_root, destination, git_ref="HEAD", allow_dirty=True)

    assert calls == [("copy", repo_root, destination)]


def test_resolve_version_prefers_git_ref_snapshot(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "VERSION").write_text("worktree-version\n", encoding="utf-8")

    def _fake_read_git_file(path, *, git_ref, relative_path):
        if relative_path == "VERSION":
            return "gitref-version\n"
        return ""

    monkeypatch.setattr(module, "read_git_file", _fake_read_git_file)

    version = module.resolve_version(repo_root, git_ref="v5.2.8")

    assert version == "gitref-version"
