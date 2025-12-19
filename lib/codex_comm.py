#!/usr/bin/env python3
"""
Codex 通信模块（日志驱动版本）
通过 FIFO 发送请求，并从 ~/.codex/sessions 下的官方日志解析回复。
"""

from __future__ import annotations

import json
import os
import re
import time
import shlex
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from terminal import get_backend_for_session, get_pane_id_from_session

SESSION_ROOT = Path(os.environ.get("CODEX_SESSION_ROOT") or (Path.home() / ".codex" / "sessions")).expanduser()
SESSION_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


class CodexLogReader:
    """读取 ~/.codex/sessions 内的 Codex 官方日志"""

    def __init__(self, root: Path = SESSION_ROOT, log_path: Optional[Path] = None, session_id_filter: Optional[str] = None):
        self.root = Path(root).expanduser()
        self._preferred_log = self._normalize_path(log_path)
        self._session_id_filter = session_id_filter
        try:
            poll = float(os.environ.get("CODEX_POLL_INTERVAL", "0.05"))
        except Exception:
            poll = 0.05
        self._poll_interval = min(0.5, max(0.01, poll))

    def set_preferred_log(self, log_path: Optional[Path]) -> None:
        self._preferred_log = self._normalize_path(log_path)

    def _normalize_path(self, value: Optional[Any]) -> Optional[Path]:
        if value in (None, ""):
            return None
        if isinstance(value, Path):
            return value
        try:
            return Path(value).expanduser()
        except TypeError:
            return None

    def _scan_latest(self) -> Optional[Path]:
        if not self.root.exists():
            return None
        try:
            # Avoid sorting the full list (can be slow on large histories / slow filesystems).
            latest: Optional[Path] = None
            latest_mtime = -1.0
            for p in (p for p in self.root.glob("**/*.jsonl") if p.is_file()):
                try:
                    if self._session_id_filter and self._session_id_filter not in p.name:
                        continue
                    mtime = p.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest = p
                    latest_mtime = mtime
        except OSError:
            return None

        return latest

    def _latest_log(self) -> Optional[Path]:
        preferred = self._preferred_log
        if preferred and preferred.exists():
            return preferred
        latest = self._scan_latest()
        if latest:
            self._preferred_log = latest
        return latest

    def current_log_path(self) -> Optional[Path]:
        return self._latest_log()

    def capture_state(self) -> Dict[str, Any]:
        """记录当前日志与偏移"""
        log = self._latest_log()
        offset = 0
        if log and log.exists():
            try:
                offset = log.stat().st_size
            except OSError:
                offset = 0
        return {"log_path": log, "offset": offset}

    def wait_for_message(self, state: Dict[str, Any], timeout: float) -> Tuple[Optional[str], Dict[str, Any]]:
        """阻塞等待新的回复"""
        return self._read_since(state, timeout, block=True)

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        """非阻塞读取回复"""
        return self._read_since(state, timeout=0.0, block=False)

    def latest_message(self) -> Optional[str]:
        """直接获取最新一条回复"""
        log_path = self._latest_log()
        if not log_path or not log_path.exists():
            return None
        try:
            with log_path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                buffer = bytearray()
                position = handle.tell()
                while position > 0 and len(buffer) < 1024 * 256:
                    read_size = min(4096, position)
                    position -= read_size
                    handle.seek(position)
                    buffer = handle.read(read_size) + buffer
                    if buffer.count(b"\n") >= 50:
                        break
                lines = buffer.decode("utf-8", errors="ignore").splitlines()
        except OSError:
            return None

        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = self._extract_message(entry)
            if message:
                return message
        return None

    def _read_since(self, state: Dict[str, Any], timeout: float, block: bool) -> Tuple[Optional[str], Dict[str, Any]]:
        deadline = time.time() + timeout
        current_path = self._normalize_path(state.get("log_path"))
        offset = state.get("offset", 0)
        # Keep rescans infrequent; new messages usually append to the same log file.
        rescan_interval = min(2.0, max(0.2, timeout / 2.0))
        last_rescan = time.time()

        def ensure_log() -> Path:
            candidates = [
                self._preferred_log if self._preferred_log and self._preferred_log.exists() else None,
                current_path if current_path and current_path.exists() else None,
            ]
            for candidate in candidates:
                if candidate:
                    return candidate
            latest = self._scan_latest()
            if latest:
                self._preferred_log = latest
                return latest
            raise FileNotFoundError("未找到 Codex session 日志")

        while True:
            try:
                log_path = ensure_log()
            except FileNotFoundError:
                if not block:
                    return None, {"log_path": None, "offset": 0}
                time.sleep(self._poll_interval)
                continue

            with log_path.open("r", encoding="utf-8", errors="ignore") as fh:
                fh.seek(offset)
                while True:
                    if block and time.time() >= deadline:
                        return None, {"log_path": log_path, "offset": offset}
                    line = fh.readline()
                    if not line:
                        break
                    offset = fh.tell()
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    message = self._extract_message(entry)
                    if message is not None:
                        return message, {"log_path": log_path, "offset": offset}

            if time.time() - last_rescan >= rescan_interval:
                latest = self._scan_latest()
                if latest and latest != log_path:
                    current_path = latest
                    self._preferred_log = latest
                    try:
                        offset = latest.stat().st_size
                    except OSError:
                        offset = 0
                    if not block:
                        return None, {"log_path": current_path, "offset": offset}
                    time.sleep(0.05)
                    last_rescan = time.time()
                    continue
                last_rescan = time.time()

            if not block:
                return None, {"log_path": log_path, "offset": offset}

            time.sleep(self._poll_interval)
            if time.time() >= deadline:
                return None, {"log_path": log_path, "offset": offset}

    @staticmethod
    def _extract_message(entry: dict) -> Optional[str]:
        if entry.get("type") != "response_item":
            return None
        payload = entry.get("payload", {})
        if payload.get("type") != "message":
            return None

        content = payload.get("content") or []
        texts = [item.get("text", "") for item in content if item.get("type") == "output_text"]
        if texts:
            return "\n".join(filter(None, texts)).strip()

        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        return None


class CodexCommunicator:
    """通过 FIFO 与 Codex 桥接器通信，并使用日志读取回复"""

    def __init__(self):
        self.session_info = self._load_session_info()
        if not self.session_info:
            raise RuntimeError("❌ 未找到活跃的Codex会话，请先运行 ccb up codex")

        self.session_id = self.session_info["session_id"]
        self.runtime_dir = Path(self.session_info["runtime_dir"])
        self.input_fifo = Path(self.session_info["input_fifo"])
        self.terminal = self.session_info.get("terminal", os.environ.get("CODEX_TERMINAL", "tmux"))
        self.pane_id = get_pane_id_from_session(self.session_info) or ""
        self.backend = get_backend_for_session(self.session_info)

        self.timeout = int(os.environ.get("CODEX_SYNC_TIMEOUT", "30"))
        self.marker_prefix = "ask"
        preferred_log = self.session_info.get("codex_session_path")
        bound_session_id = self.session_info.get("codex_session_id")
        self.log_reader = CodexLogReader(log_path=preferred_log, session_id_filter=bound_session_id)
        self.project_session_file = self.session_info.get("_session_file")

        self._prime_log_binding()

        healthy, msg = self._check_session_health()
        if not healthy:
            raise RuntimeError(f"❌ 会话不健康: {msg}\n提示: 请运行 ccb up codex 启动新会话")

    def _load_session_info(self):
        if "CODEX_SESSION_ID" in os.environ:
            terminal = os.environ.get("CODEX_TERMINAL", "tmux")
            # 根据终端类型获取正确的 pane_id
            if terminal == "wezterm":
                pane_id = os.environ.get("CODEX_WEZTERM_PANE", "")
            elif terminal == "iterm2":
                pane_id = os.environ.get("CODEX_ITERM2_PANE", "")
            else:
                pane_id = ""
            return {
                "session_id": os.environ["CODEX_SESSION_ID"],
                "runtime_dir": os.environ["CODEX_RUNTIME_DIR"],
                "input_fifo": os.environ["CODEX_INPUT_FIFO"],
                "output_fifo": os.environ.get("CODEX_OUTPUT_FIFO", ""),
                "terminal": terminal,
                "tmux_session": os.environ.get("CODEX_TMUX_SESSION", ""),
                "pane_id": pane_id,
                "_session_file": None,
            }

        project_session = Path.cwd() / ".codex-session"
        if not project_session.exists():
            return None

        try:
            with open(project_session, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                return None

            if not data.get("active", False):
                return None

            runtime_dir = Path(data.get("runtime_dir", ""))
            if not runtime_dir.exists():
                return None

            data["_session_file"] = str(project_session)
            return data

        except Exception:
            return None

    def _prime_log_binding(self) -> None:
        """确保在会话启动时尽早绑定日志路径和会话ID"""
        log_hint = self.log_reader.current_log_path()
        if not log_hint:
            return
        self._remember_codex_session(log_hint)

    def _check_session_health(self):
        return self._check_session_health_impl(probe_terminal=True)

    def _check_session_health_impl(self, probe_terminal: bool):
        try:
            if not self.runtime_dir.exists():
                return False, "运行时目录不存在"

            # WezTerm/iTerm2 模式：没有 tmux wrapper，因此通常不会生成 codex.pid；
            # 以 pane 存活作为健康判定（与 Gemini 逻辑一致）。
            if self.terminal in ("wezterm", "iterm2"):
                if not self.pane_id:
                    return False, f"未找到 {self.terminal} pane_id"
                if probe_terminal and (not self.backend or not self.backend.is_alive(self.pane_id)):
                    return False, f"{self.terminal} pane 不存在: {self.pane_id}"
                return True, "会话正常"

            # tmux 模式：检查 tmux 会话是否存活
            # 注意：不再检查 codex.pid，因为 wrapper.sh 使用 exec tmux attach 后 PID 会失效
            tmux_session = self.session_info.get("tmux_session")
            if tmux_session and probe_terminal:
                import subprocess
                result = subprocess.run(
                    ["tmux", "has-session", "-t", tmux_session],
                    capture_output=True
                )
                if result.returncode != 0:
                    return False, f"Tmux会话不存在: {tmux_session}"

            if not self.input_fifo.exists():
                return False, "通信管道不存在"

            return True, "会话正常"
        except Exception as exc:
            return False, f"检查失败: {exc}"

    def _send_via_terminal(self, content: str) -> None:
        if not self.backend or not self.pane_id:
            raise RuntimeError("未配置终端会话")
        self.backend.send_text(self.pane_id, content)

    def _send_message(self, content: str) -> Tuple[str, Dict[str, Any]]:
        marker = self._generate_marker()
        message = {
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "marker": marker,
        }

        state = self.log_reader.capture_state()

        # tmux 模式优先通过 FIFO 驱动桥接器；WezTerm/iTerm2 模式则直接向 pane 注入文本
        if self.terminal in ("wezterm", "iterm2"):
            self._send_via_terminal(content)
        else:
            with open(self.input_fifo, "w", encoding="utf-8") as fifo:
                fifo.write(json.dumps(message, ensure_ascii=False) + "\n")
                fifo.flush()

        return marker, state

    def _generate_marker(self) -> str:
        return f"{self.marker_prefix}-{int(time.time())}-{os.getpid()}"

    def ask_async(self, question: str) -> bool:
        try:
            healthy, status = self._check_session_health_impl(probe_terminal=False)
            if not healthy:
                raise RuntimeError(f"❌ 会话异常: {status}")

            marker, state = self._send_message(question)
            log_hint = state.get("log_path") or self.log_reader.current_log_path()
            self._remember_codex_session(log_hint)
            print(f"✅ 已发送到Codex (标记: {marker[:12]}...)")
            print("提示: 使用 /cpend 查看最新回复")
            return True
        except Exception as exc:
            print(f"❌ 发送失败: {exc}")
            return False

    def ask_sync(self, question: str, timeout: Optional[int] = None) -> Optional[str]:
        try:
            healthy, status = self._check_session_health_impl(probe_terminal=False)
            if not healthy:
                raise RuntimeError(f"❌ 会话异常: {status}")

            print("🔔 发送问题到Codex...")
            marker, state = self._send_message(question)
            wait_timeout = self.timeout if timeout is None else int(timeout)
            if wait_timeout == 0:
                print("⏳ 等待 Codex 回复 (无超时，Ctrl-C 可中断)...")
                start_time = time.time()
                last_hint = 0
                while True:
                    message, new_state = self.log_reader.wait_for_message(state, timeout=30.0)
                    state = new_state or state
                    log_hint = (new_state or {}).get("log_path") if isinstance(new_state, dict) else None
                    if not log_hint:
                        log_hint = self.log_reader.current_log_path()
                    self._remember_codex_session(log_hint)
                    if message:
                        print("🤖 Codex回复:")
                        print(message)
                        return message
                    elapsed = int(time.time() - start_time)
                    if elapsed >= last_hint + 30:
                        last_hint = elapsed
                        print(f"⏳ 仍在等待... ({elapsed}s)")

            print(f"⏳ 等待Codex回复 (超时 {wait_timeout} 秒)...")
            message, new_state = self.log_reader.wait_for_message(state, float(wait_timeout))
            log_hint = (new_state or {}).get("log_path") if isinstance(new_state, dict) else None
            if not log_hint:
                log_hint = self.log_reader.current_log_path()
            self._remember_codex_session(log_hint)
            if message:
                print("🤖 Codex回复:")
                print(message)
                return message

            print("⏰ Codex未在限定时间内回复，可稍后执行 /cpend 获取最新答案")
            return None
        except Exception as exc:
            print(f"❌ 同步询问失败: {exc}")
            return None

    def consume_pending(self, display: bool = True):
        current_path = self.log_reader.current_log_path()
        self._remember_codex_session(current_path)
        message = self.log_reader.latest_message()
        if message:
            self._remember_codex_session(self.log_reader.current_log_path())
        if not message:
            if display:
                print("暂无 Codex 回复")
            return None
        if display:
            print(message)
        return message

    def ping(self, display: bool = True) -> Tuple[bool, str]:
        healthy, status = self._check_session_health()
        msg = f"✅ Codex连接正常 ({status})" if healthy else f"❌ Codex连接异常: {status}"
        if display:
            print(msg)
        return healthy, msg

    def get_status(self) -> Dict[str, Any]:
        healthy, status = self._check_session_health()
        info = {
            "session_id": self.session_id,
            "runtime_dir": str(self.runtime_dir),
            "healthy": healthy,
            "status": status,
            "input_fifo": str(self.input_fifo),
        }

        codex_pid_file = self.runtime_dir / "codex.pid"
        if codex_pid_file.exists():
            with open(codex_pid_file, "r", encoding="utf-8") as f:
                info["codex_pid"] = int(f.read().strip())

        return info

    def _remember_codex_session(self, log_path: Optional[Path]) -> None:
        if not log_path:
            log_path = self.log_reader.current_log_path()
            if not log_path:
                return

        try:
            log_path_obj = log_path if isinstance(log_path, Path) else Path(str(log_path)).expanduser()
        except Exception:
            return

        self.log_reader.set_preferred_log(log_path_obj)

        if not self.project_session_file:
            return

        project_file = Path(self.project_session_file)
        if not project_file.exists():
            return
        try:
            with project_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return

        path_str = str(log_path_obj)
        session_id = self._extract_session_id(log_path_obj)
        resume_cmd = f"codex resume {session_id}" if session_id else None
        updated = False

        if data.get("codex_session_path") != path_str:
            data["codex_session_path"] = path_str
            updated = True
        if session_id and data.get("codex_session_id") != session_id:
            data["codex_session_id"] = session_id
            updated = True
        if resume_cmd:
            if data.get("codex_start_cmd") != resume_cmd:
                data["codex_start_cmd"] = resume_cmd
                updated = True
        elif data.get("codex_start_cmd", "").startswith("codex resume "):
            # keep existing command if we cannot derive a better one
            pass
        if data.get("active") is False:
            data["active"] = True
            updated = True

        if updated:
            tmp_file = project_file.with_suffix(".tmp")
            try:
                with tmp_file.open("w", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False, indent=2)
                os.replace(tmp_file, project_file)
            except Exception:
                if tmp_file.exists():
                    tmp_file.unlink(missing_ok=True)

        self.session_info["codex_session_path"] = path_str
        if session_id:
            self.session_info["codex_session_id"] = session_id
        if resume_cmd:
            self.session_info["codex_start_cmd"] = resume_cmd

    @staticmethod
    def _extract_session_id(log_path: Path) -> Optional[str]:
        for source in (log_path.stem, log_path.name):
            match = SESSION_ID_PATTERN.search(source)
            if match:
                return match.group(0)

        try:
            with log_path.open("r", encoding="utf-8") as handle:
                first_line = handle.readline()
        except OSError:
            return None

        if not first_line:
            return None

        match = SESSION_ID_PATTERN.search(first_line)
        if match:
            return match.group(0)

        try:
            entry = json.loads(first_line)
        except Exception:
            return None

        payload = entry.get("payload", {}) if isinstance(entry, dict) else {}
        candidates = [
            entry.get("session_id") if isinstance(entry, dict) else None,
            payload.get("id") if isinstance(payload, dict) else None,
            payload.get("session", {}).get("id") if isinstance(payload, dict) else None,
        ]
        for candidate in candidates:
            if isinstance(candidate, str):
                match = SESSION_ID_PATTERN.search(candidate)
                if match:
                    return match.group(0)
        return None


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Codex 通信工具（日志驱动）")
    parser.add_argument("question", nargs="*", help="要发送的问题")
    parser.add_argument("--wait", "-w", action="store_true", help="同步等待回复")
    parser.add_argument("--timeout", type=int, default=30, help="同步超时时间(秒)")
    parser.add_argument("--ping", action="store_true", help="测试连通性")
    parser.add_argument("--status", action="store_true", help="查看状态")
    parser.add_argument("--pending", action="store_true", help="查看待处理回复")

    args = parser.parse_args()

    try:
        comm = CodexCommunicator()

        if args.ping:
            comm.ping()
        elif args.status:
            status = comm.get_status()
            print("📊 Codex状态:")
            for key, value in status.items():
                print(f"   {key}: {value}")
        elif args.pending:
            comm.consume_pending()
        elif args.question:
            tokens = list(args.question)
            if tokens and tokens[0].lower() == "ask":
                tokens = tokens[1:]
            question_text = " ".join(tokens).strip()
            if not question_text:
                print("❌ 请提供问题内容")
                return 1
            if args.wait:
                comm.ask_sync(question_text, args.timeout)
            else:
                comm.ask_async(question_text)
        else:
            print("请提供问题或使用 --ping/--status/--pending 选项")
            return 1
        return 0
    except Exception as exc:
        print(f"❌ 执行失败: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
