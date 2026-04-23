from __future__ import annotations

import multiprocessing as mp
import threading
import time
from pathlib import Path

from storage import atomic as atomic_module


def _write_many(target: str, token: str, started, count: int) -> None:
    started.wait(timeout=5)
    path = Path(target)
    for index in range(count):
        atomic_module.atomic_write_text(path, f"{token}-{index}\n")
        time.sleep(0.001)


def test_atomic_write_text_serializes_same_target(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / 'runtime.json'
    replace_guard = threading.Lock()
    overlaps: list[tuple[str, str]] = []
    errors: list[Exception] = []
    real_replace = atomic_module.os.replace

    def _replace(src: str, dst: str) -> None:
        if not replace_guard.acquire(blocking=False):
            overlaps.append((src, dst))
            raise AssertionError('concurrent os.replace on same target')
        try:
            time.sleep(0.01)
            real_replace(src, dst)
        finally:
            replace_guard.release()

    monkeypatch.setattr(atomic_module.os, 'replace', _replace)

    def _writer(index: int) -> None:
        try:
            atomic_module.atomic_write_text(target, f'value={index}\n')
        except Exception as exc:  # pragma: no cover - exercised via assertion
            errors.append(exc)

    threads = [threading.Thread(target=_writer, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)
        assert not thread.is_alive()

    assert overlaps == []
    assert errors == []
    assert target.read_text(encoding='utf-8').startswith('value=')


def test_atomic_write_text_serializes_across_processes(tmp_path: Path) -> None:
    target = tmp_path / 'lease.json'
    ctx = mp.get_context('spawn')
    started = ctx.Event()
    processes = [
        ctx.Process(target=_write_many, args=(str(target), f'worker{index}', started, 40))
        for index in range(2)
    ]

    for process in processes:
        process.start()
    started.set()
    for process in processes:
        process.join(timeout=10)
        assert not process.is_alive()
        assert process.exitcode == 0

    text = target.read_text(encoding='utf-8').strip()
    assert text.startswith('worker')
