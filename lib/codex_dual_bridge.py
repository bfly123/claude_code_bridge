#!/usr/bin/env python3
"""
Codex 双窗口桥接器
负责发送命令到 Codex，支持 tmux 和 WezTerm。
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from terminal import TmuxBackend, WeztermBackend


class TerminalCodexSession:
    """通过终端会话向 Codex CLI 注入指令"""

    def __init__(self, terminal_type: str, pane_id: str):
        self.terminal_type = terminal_type
        self.pane_id = pane_id
        self.backend = WeztermBackend() if terminal_type == "wezterm" else TmuxBackend()

    def send(self, text: str) -> None:
        command = text.replace("\r", " ").replace("\n", " ").strip()
        if command:
            self.backend.send_text(self.pane_id, command)


class DualBridge:
    """Claude ↔ Codex 桥接主流程"""

    def __init__(self, runtime_dir: Path, session_id: str):
        self.runtime_dir = runtime_dir
        self.session_id = session_id
        self.input_fifo = self.runtime_dir / "input.fifo"
        self.history_dir = self.runtime_dir / "history"
        self.history_file = self.history_dir / "session.jsonl"
        self.bridge_log = self.runtime_dir / "bridge.log"
        self.history_dir.mkdir(parents=True, exist_ok=True)

        terminal_type = os.environ.get("CODEX_TERMINAL", "tmux")
        pane_id = os.environ.get("CODEX_WEZTERM_PANE") if terminal_type == "wezterm" else os.environ.get("CODEX_TMUX_SESSION")
        
        # If pane_id not in env, try to read from .codex-session file
        if not pane_id and terminal_type == "tmux":
            session_file = Path.cwd() / ".codex-session"
            if session_file.exists():
                try:
                    data = json.loads(session_file.read_text())
                    pane_id = data.get("tmux_session")
                except Exception:
                    pass
        
        if not pane_id:
            raise RuntimeError(f"缺少 {'CODEX_WEZTERM_PANE' if terminal_type == 'wezterm' else 'CODEX_TMUX_SESSION'} 环境变量")

        self.codex_session = TerminalCodexSession(terminal_type, pane_id)
        self._running = True
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, _: Any) -> None:
        self._running = False
        self._log_console(f"⚠️ 收到信号 {signum}，准备退出...")

    def run(self) -> int:
        self._log_console("🔌 Codex桥接器已启动，等待Claude指令...")
        while self._running:
            try:
                payload = self._read_request()
                if payload is None:
                    time.sleep(0.1)
                    continue
                self._process_request(payload)
            except KeyboardInterrupt:
                self._running = False
            except Exception as exc:
                self._log_console(f"❌ 处理消息失败: {exc}")
                self._log_bridge(f"error: {exc}")
                time.sleep(0.5)

        self._log_console("👋 Codex桥接器已退出")
        return 0

    def _read_request(self) -> Optional[Dict[str, Any]]:
        if not self.input_fifo.exists():
            return None
        try:
            with self.input_fifo.open("r", encoding="utf-8") as fifo:
                line = fifo.readline()
                if not line:
                    return None
                return json.loads(line)
        except json.JSONDecodeError:
            return None

    def _process_request(self, payload: Dict[str, Any]) -> None:
        content = payload.get("content", "")
        marker = payload.get("marker") or self._generate_marker()

        timestamp = self._timestamp()
        self._log_bridge(json.dumps({"marker": marker, "question": content, "time": timestamp}, ensure_ascii=False))
        self._append_history("claude", content, marker)

        try:
            self.codex_session.send(content)
        except Exception as exc:
            msg = f"❌ 发送至 Codex 失败: {exc}"
            self._append_history("codex", msg, marker)
            self._log_console(msg)

    def _append_history(self, role: str, content: str, marker: str) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "marker": marker,
            "content": content,
        }
        try:
            with self.history_file.open("a", encoding="utf-8") as handle:
                json.dump(entry, handle, ensure_ascii=False)
                handle.write("\n")
        except Exception as exc:
            self._log_console(f"⚠️ 写入历史失败: {exc}")

    def _log_bridge(self, message: str) -> None:
        try:
            with self.bridge_log.open("a", encoding="utf-8") as handle:
                handle.write(f"{self._timestamp()} {message}\n")
        except Exception:
            pass

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _generate_marker() -> str:
        return f"ask-{int(time.time())}-{os.getpid()}"

    @staticmethod
    def _log_console(message: str) -> None:
        print(message, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claude-Codex 桥接器")
    parser.add_argument("--runtime-dir", required=True, help="运行目录")
    parser.add_argument("--session-id", required=True, help="会话ID")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir)
    bridge = DualBridge(runtime_dir, args.session_id)
    return bridge.run()


if __name__ == "__main__":
    raise SystemExit(main())
