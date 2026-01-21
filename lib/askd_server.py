from __future__ import annotations

import json
import os
import socketserver
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from askd_runtime import log_path, normalize_connect_host, run_dir, write_log
from process_lock import ProviderLock
from providers import ProviderDaemonSpec
from session_utils import safe_write_session

RequestHandler = Callable[[dict], dict]


def _env_truthy(name: str) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _env_parent_pid() -> Optional[int]:
    raw = (os.environ.get("CCB_PARENT_PID") or "").strip()
    if not raw:
        return None
    try:
        pid = int(raw)
    except Exception:
        return None
    return pid if pid > 0 else None


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class AskDaemonServer:
    def __init__(
        self,
        *,
        spec: ProviderDaemonSpec,
        host: str = "127.0.0.1",
        port: int = 0,
        token: str,
        state_file: Path,
        request_handler: RequestHandler,
        request_queue_size: Optional[int] = None,
        on_stop: Optional[Callable[[], None]] = None,
        parent_pid: Optional[int] = None,
        managed: Optional[bool] = None,
    ):
        self.spec = spec
        self.host = host
        self.port = port
        self.token = token
        self.state_file = state_file
        self.request_handler = request_handler
        self.request_queue_size = request_queue_size
        self.on_stop = on_stop
        self.parent_pid = parent_pid if parent_pid is not None else _env_parent_pid()
        env_managed = _env_truthy("CCB_MANAGED")
        self.managed = env_managed if managed is None else bool(managed)
        if self.parent_pid:
            self.managed = True

    def serve_forever(self) -> int:
        run_dir().mkdir(parents=True, exist_ok=True)

        lock = ProviderLock(self.spec.lock_name, cwd=str(self.state_file.parent), timeout=0.1)
        if not lock.try_acquire():
            return 2

        protocol_prefix = self.spec.protocol_prefix
        response_type = f"{protocol_prefix}.response"

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                with self.server.activity_lock:
                    self.server.active_requests += 1
                    self.server.last_activity = time.time()

                try:
                    line = self.rfile.readline()
                    if not line:
                        return
                    msg = json.loads(line.decode("utf-8", errors="replace"))
                except Exception:
                    return

                if msg.get("token") != self.server.token:
                    self._write({"type": response_type, "v": 1, "id": msg.get("id"), "exit_code": 1, "reply": "Unauthorized"})
                    return

                msg_type = msg.get("type")
                if msg_type == f"{protocol_prefix}.ping":
                    self._write({"type": f"{protocol_prefix}.pong", "v": 1, "id": msg.get("id"), "exit_code": 0, "reply": "OK"})
                    return

                if msg_type == f"{protocol_prefix}.shutdown":
                    self._write({"type": response_type, "v": 1, "id": msg.get("id"), "exit_code": 0, "reply": "OK"})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return

                if msg_type != f"{protocol_prefix}.request":
                    self._write({"type": response_type, "v": 1, "id": msg.get("id"), "exit_code": 1, "reply": "Invalid request"})
                    return

                try:
                    resp = self.server.request_handler(msg)
                except Exception as exc:
                    try:
                        write_log(log_path(self.server.spec.log_file_name), f"[ERROR] request handler error: {exc}")
                    except Exception:
                        pass
                    self._write({"type": response_type, "v": 1, "id": msg.get("id"), "exit_code": 1, "reply": f"Internal error: {exc}"})
                    return

                if isinstance(resp, dict):
                    self._write(resp)
                else:
                    self._write({"type": response_type, "v": 1, "id": msg.get("id"), "exit_code": 1, "reply": "Invalid response"})

            def _write(self, obj: dict) -> None:
                try:
                    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
                    self.wfile.write(data)
                    self.wfile.flush()
                    try:
                        with self.server.activity_lock:
                            self.server.last_activity = time.time()
                    except Exception:
                        pass
                except Exception:
                    pass

            def finish(self) -> None:
                try:
                    super().finish()
                finally:
                    try:
                        with self.server.activity_lock:
                            if self.server.active_requests > 0:
                                self.server.active_requests -= 1
                            self.server.last_activity = time.time()
                    except Exception:
                        pass

        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = True

        if self.request_queue_size is not None:
            try:
                Server.request_queue_size = int(self.request_queue_size)
            except Exception:
                pass

        try:
            with Server((self.host, self.port), Handler) as httpd:
                httpd.spec = self.spec
                httpd.token = self.token
                httpd.request_handler = self.request_handler
                httpd.active_requests = 0
                httpd.last_activity = time.time()
                httpd.activity_lock = threading.Lock()
                try:
                    httpd.idle_timeout_s = float(os.environ.get(self.spec.idle_timeout_env, "60") or "60")
                except Exception:
                    httpd.idle_timeout_s = 60.0
                httpd.managed = bool(self.managed)
                httpd.parent_pid = int(self.parent_pid or 0)
                if httpd.managed:
                    httpd.idle_timeout_s = 0.0

                def _idle_monitor() -> None:
                    timeout_s = float(getattr(httpd, "idle_timeout_s", 60.0) or 0.0)
                    if timeout_s <= 0:
                        return
                    while True:
                        time.sleep(0.5)
                        try:
                            with httpd.activity_lock:
                                active = int(httpd.active_requests or 0)
                                last = float(httpd.last_activity or time.time())
                        except Exception:
                            active = 0
                            last = time.time()
                        if active == 0 and (time.time() - last) >= timeout_s:
                            write_log(
                                log_path(self.spec.log_file_name),
                                f"[INFO] {self.spec.daemon_key} idle timeout ({int(timeout_s)}s) reached; shutting down",
                            )
                            threading.Thread(target=httpd.shutdown, daemon=True).start()
                            return

                threading.Thread(target=_idle_monitor, daemon=True).start()

                if getattr(httpd, "parent_pid", 0):
                    parent_pid = int(httpd.parent_pid or 0)

                    def _parent_monitor() -> None:
                        while True:
                            time.sleep(0.5)
                            if not _is_pid_alive(parent_pid):
                                write_log(
                                    log_path(self.spec.log_file_name),
                                    f"[INFO] {self.spec.daemon_key} parent pid {parent_pid} exited; shutting down",
                                )
                                threading.Thread(target=httpd.shutdown, daemon=True).start()
                                return

                    threading.Thread(target=_parent_monitor, daemon=True).start()

                actual_host, actual_port = httpd.server_address
                self._write_state(str(actual_host), int(actual_port))
                write_log(
                    log_path(self.spec.log_file_name),
                    f"[INFO] {self.spec.daemon_key} started pid={os.getpid()} addr={actual_host}:{actual_port}",
                )
                try:
                    httpd.serve_forever(poll_interval=0.2)
                finally:
                    write_log(log_path(self.spec.log_file_name), f"[INFO] {self.spec.daemon_key} stopped")
                    if self.on_stop:
                        try:
                            self.on_stop()
                        except Exception:
                            pass
        finally:
            try:
                lock.release()
            except Exception:
                pass
        return 0

    def _write_state(self, host: str, port: int) -> None:
        payload = {
            "pid": os.getpid(),
            "host": host,
            "connect_host": normalize_connect_host(host),
            "port": port,
            "token": self.token,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "python": sys.executable,
            "parent_pid": int(self.parent_pid or 0) or None,
            "managed": bool(self.managed),
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        ok, _err = safe_write_session(self.state_file, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        if ok:
            if os.name != "nt":
                try:
                    os.chmod(self.state_file, 0o600)
                except Exception:
                    pass
