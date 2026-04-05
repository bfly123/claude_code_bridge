from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable


@dataclass
class TmuxPaneService:
    tmux_run_fn: Callable[..., object]
    looks_like_pane_id_fn: Callable[[str], bool]
    normalize_split_direction_fn: Callable[[str], tuple[str, str]]
    pane_exists_output_fn: Callable[[str], bool]
    pane_id_by_title_marker_output_fn: Callable[[str, str], str | None]
    pane_is_alive_fn: Callable[[str], bool]
    normalize_user_option_fn: Callable[[str], str]
    strip_ansi_fn: Callable[[str], str]

    def pane_exists(self, pane_id: str) -> bool:
        if not self.looks_like_pane_id_fn(pane_id):
            return False
        try:
            cp = self.tmux_run_fn(['display-message', '-p', '-t', pane_id, '#{pane_id}'], capture=True, timeout=0.5)
            return getattr(cp, 'returncode', 1) == 0 and self.pane_exists_output_fn(getattr(cp, 'stdout', '') or '')
        except Exception:
            return False

    def get_current_pane_id(self, *, env_pane: str) -> str:
        env_pane = (env_pane or '').strip()
        if self.looks_like_pane_id_fn(env_pane) and self.pane_exists(env_pane):
            return env_pane
        try:
            cp = self.tmux_run_fn(['display-message', '-p', '#{pane_id}'], capture=True, timeout=0.5)
            out = (getattr(cp, 'stdout', '') or '').strip()
            if self.looks_like_pane_id_fn(out) and self.pane_exists(out):
                return out
        except Exception:
            pass
        raise RuntimeError('tmux current pane id not available')

    def split_pane(self, parent_pane_id: str, *, direction: str, percent: int) -> str:
        if not parent_pane_id:
            raise ValueError('parent_pane_id is required')
        try:
            if self.looks_like_pane_id_fn(parent_pane_id):
                zoom_cp = self.tmux_run_fn(
                    ['display-message', '-p', '-t', parent_pane_id, '#{window_zoomed_flag}'],
                    capture=True,
                    timeout=0.5,
                )
                if getattr(zoom_cp, 'returncode', 1) == 0 and (getattr(zoom_cp, 'stdout', '') or '').strip() in ('1', 'on', 'yes', 'true'):
                    self.tmux_run_fn(['resize-pane', '-Z', '-t', parent_pane_id], check=False, timeout=0.5)
        except Exception:
            pass

        if self.looks_like_pane_id_fn(parent_pane_id) and not self.pane_exists(parent_pane_id):
            raise RuntimeError(f'Cannot split: pane {parent_pane_id} does not exist')

        size_cp = self.tmux_run_fn(
            ['display-message', '-p', '-t', parent_pane_id, '#{pane_width}x#{pane_height}'],
            capture=True,
        )
        pane_size = (getattr(size_cp, 'stdout', '') or '').strip() if getattr(size_cp, 'returncode', 1) == 0 else 'unknown'
        flag, direction_norm = self.normalize_split_direction_fn(direction)
        split_percent = max(1, min(99, int(percent or 50)))
        try:
            cp = self.tmux_run_fn(
                ['split-window', flag, '-p', str(split_percent), '-t', parent_pane_id, '-P', '-F', '#{pane_id}'],
                check=True,
                capture=True,
            )
        except subprocess.CalledProcessError as e:
            out = (getattr(e, 'stdout', '') or '').strip()
            err = (getattr(e, 'stderr', '') or '').strip()
            msg = err or out
            raise RuntimeError(
                f"tmux split-window failed (exit {e.returncode}): {msg or 'no stdout/stderr'}\n"
                f"Pane: {parent_pane_id}, size: {pane_size}, direction: {direction_norm}\n"
                f"Command: {' '.join(e.cmd)}\n"
                f"Hint: If the pane is zoomed, press Prefix+z to unzoom; also try enlarging terminal window."
            ) from e
        pane_id = (getattr(cp, 'stdout', '') or '').strip()
        if not self.looks_like_pane_id_fn(pane_id):
            raise RuntimeError(f'tmux split-window did not return pane_id: {pane_id!r}')
        return pane_id

    def set_pane_title(self, pane_id: str, title: str) -> None:
        if not pane_id:
            return
        self.tmux_run_fn(['select-pane', '-t', pane_id, '-T', title or ''], check=False)

    def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
        if not pane_id:
            return
        opt = self.normalize_user_option_fn(name)
        if not opt:
            return
        self.tmux_run_fn(['set-option', '-p', '-t', pane_id, opt, value or ''], check=False)

    def set_pane_style(
        self,
        pane_id: str,
        *,
        border_style: str | None = None,
        active_border_style: str | None = None,
    ) -> None:
        if not pane_id:
            return
        if border_style:
            self.tmux_run_fn(['set-option', '-p', '-t', pane_id, 'pane-border-style', border_style], check=False)
        if active_border_style:
            self.tmux_run_fn(
                ['set-option', '-p', '-t', pane_id, 'pane-active-border-style', active_border_style],
                check=False,
            )

    def find_pane_by_title_marker(self, marker: str) -> str | None:
        marker = (marker or '').strip()
        if not marker:
            return None
        cp = self.tmux_run_fn(['list-panes', '-a', '-F', '#{pane_id}\t#{pane_title}'], capture=True)
        if getattr(cp, 'returncode', 1) != 0:
            return None
        return self.pane_id_by_title_marker_output_fn(getattr(cp, 'stdout', '') or '', marker)

    def find_pane_by_user_options(self, expected: dict[str, str]) -> str | None:
        matches = self.list_panes_by_user_options(expected)
        if len(matches) == 1:
            return matches[0]
        return None

    def list_panes_by_user_options(self, expected: dict[str, str]) -> list[str]:
        normalized: list[tuple[str, str]] = []
        seen: set[str] = set()
        for name, value in dict(expected or {}).items():
            opt = self.normalize_user_option_fn(str(name))
            text = str(value or '').strip()
            if not opt or not text or opt in seen:
                continue
            seen.add(opt)
            normalized.append((opt, text))
        if not normalized:
            return []

        format_parts = ['#{pane_id}']
        for opt, _ in normalized:
            format_parts.append(f'#{{{opt}}}')
        cp = self.tmux_run_fn(['list-panes', '-a', '-F', '\t'.join(format_parts)], capture=True)
        if getattr(cp, 'returncode', 1) != 0:
            return []

        matches: list[str] = []
        for line in (getattr(cp, 'stdout', '') or '').splitlines():
            parts = line.split('\t')
            if len(parts) != len(normalized) + 1:
                continue
            pane_id = parts[0].strip()
            if not self.looks_like_pane_id_fn(pane_id):
                continue
            ok = True
            for index, (_, expected_value) in enumerate(normalized, start=1):
                if (parts[index] or '').strip() != expected_value:
                    ok = False
                    break
            if ok:
                matches.append(pane_id)
        return matches

    def describe_pane(self, pane_id: str, *, user_options: tuple[str, ...] = ()) -> dict[str, str] | None:
        if not self.looks_like_pane_id_fn(pane_id):
            return None
        normalized_options: list[str] = []
        seen: set[str] = set()
        for name in tuple(user_options or ()):
            opt = self.normalize_user_option_fn(str(name))
            if not opt or opt in seen:
                continue
            seen.add(opt)
            normalized_options.append(opt)

        format_parts = ['#{pane_id}', '#{pane_title}', '#{pane_dead}']
        for opt in normalized_options:
            format_parts.append(f'#{{{opt}}}')
        cp = self.tmux_run_fn(
            ['display-message', '-p', '-t', pane_id, '\t'.join(format_parts)],
            capture=True,
            timeout=0.5,
        )
        if getattr(cp, 'returncode', 1) != 0:
            return None
        line = ((getattr(cp, 'stdout', '') or '').splitlines() or [''])[0]
        parts = line.split('\t')
        if len(parts) != len(format_parts):
            return None
        described = {
            'pane_id': parts[0].strip(),
            'pane_title': parts[1],
            'pane_dead': parts[2].strip(),
        }
        for index, opt in enumerate(normalized_options, start=3):
            described[opt] = (parts[index] or '').strip()
        return described

    def get_pane_content(self, pane_id: str, *, lines: int = 20) -> str | None:
        if not pane_id:
            return None
        n = max(1, int(lines))
        cp = self.tmux_run_fn(['capture-pane', '-t', pane_id, '-p', '-S', f'-{n}'], capture=True)
        if getattr(cp, 'returncode', 1) != 0:
            return None
        return self.strip_ansi_fn(getattr(cp, 'stdout', '') or '')

    def is_pane_alive(self, pane_id: str) -> bool:
        if not pane_id:
            return False
        cp = self.tmux_run_fn(['display-message', '-p', '-t', pane_id, '#{pane_dead}'], capture=True)
        if getattr(cp, 'returncode', 1) != 0:
            return False
        return self.pane_is_alive_fn(getattr(cp, 'stdout', '') or '')
