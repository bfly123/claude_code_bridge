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
    ):
        self.spec = spec
        self.host = host
        self.port = port
        self.token = token
        self.state_file = state_file
        self.request_handler = request_handler
        self.request_queue_size = request_queue_size
        self.on_stop = on_stop

    def serve_forever(self) -> int:
        run_dir().mkdir(parents=True, exist_ok=True)

        lock = ProviderLock(self.spec.lock_name, cwd="global", timeout=0.1)
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
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        ok, _err = safe_write_session(self.state_file, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        if ok:
            if os.name != "nt":
                try:
                    os.chmod(self.state_file, 0o600)
                except Exception:
                    pass
