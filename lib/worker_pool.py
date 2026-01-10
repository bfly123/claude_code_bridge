from __future__ import annotations

import queue
import threading
from typing import Callable, Generic, Optional, Protocol, TypeVar


ResultT = TypeVar("ResultT")


class QueuedTaskLike(Protocol[ResultT]):
    req_id: str
    done_event: threading.Event
    result: Optional[ResultT]


TaskT = TypeVar("TaskT", bound=QueuedTaskLike)


class BaseSessionWorker(threading.Thread, Generic[TaskT, ResultT]):
    def __init__(self, session_key: str):
        super().__init__(daemon=True)
        self.session_key = session_key
        self._q: "queue.Queue[TaskT]" = queue.Queue()
        self._stop_event = threading.Event()

    def enqueue(self, task: TaskT) -> None:
        self._q.put(task)

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                task = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                task.result = self._handle_task(task)
            except Exception as exc:
                task.result = self._handle_exception(exc, task)
            finally:
                task.done_event.set()

    def _handle_task(self, task: TaskT) -> ResultT:
        raise NotImplementedError

    def _handle_exception(self, exc: Exception, task: TaskT) -> ResultT:
        raise NotImplementedError


WorkerT = TypeVar("WorkerT", bound=threading.Thread)


class PerSessionWorkerPool(Generic[WorkerT]):
    def __init__(self):
        self._lock = threading.Lock()
        self._workers: dict[str, WorkerT] = {}

    def get_or_create(self, session_key: str, factory: Callable[[str], WorkerT]) -> WorkerT:
        created = False
        with self._lock:
            worker = self._workers.get(session_key)
            if worker is None:
                worker = factory(session_key)
                self._workers[session_key] = worker
                created = True
        if created:
            worker.start()
        return worker
