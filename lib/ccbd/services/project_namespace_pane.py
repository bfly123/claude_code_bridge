from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from terminal_runtime.tmux_readiness import (
    TmuxTransientServerUnavailable,
    is_tmux_transient_server_error_text,
    tmux_failure_detail,
)


@dataclass(frozen=True)
class ProjectNamespacePaneRecord:
    pane_id: str
    session_name: str | None = None
    window_id: str | None = None
    window_name: str | None = None
    role: str | None = None
    slot_key: str | None = None
    project_id: str | None = None
    managed_by: str | None = None
    namespace_epoch: int | None = None
    alive: bool = False

    @staticmethod
    def _matches_field(actual: str | None, expected: str, *, allow_missing: bool = False) -> bool:
        if allow_missing and actual is None:
            return True
        return str(actual or '').strip() == str(expected or '').strip()

    def matches(
        self,
        *,
        tmux_session_name: str,
        project_id: str,
        role: str,
        slot_key: str | None = None,
        managed_by: str | None = 'ccbd',
        window_id: str | None = None,
    ) -> bool:
        if not self._matches_field(
            self.session_name,
            tmux_session_name or '',
            allow_missing=True,
        ):
            return False
        if not self._matches_field(self.project_id, project_id):
            return False
        if not self._matches_field(self.role, role):
            return False
        if slot_key is not None and not self._matches_field(self.slot_key, slot_key):
            return False
        if managed_by is not None and not self._matches_field(self.managed_by, managed_by):
            return False
        if window_id is not None and not self._matches_field(self.window_id, window_id):
            return False
        return bool(self.alive)


def inspect_project_namespace_pane(backend, pane_id: str) -> ProjectNamespacePaneRecord | None:
    pane_text = str(pane_id or '').strip()
    if not pane_text.startswith('%'):
        return None
    details = _describe_pane_via_tmux(backend, pane_text)
    if details is None:
        details = _describe_pane_via_backend(backend, pane_text)
    if details is None:
        return None
    return ProjectNamespacePaneRecord(
        pane_id=pane_text,
        session_name=_clean(details.get('session_name')),
        window_id=_clean(details.get('window_id')),
        window_name=_clean(details.get('window_name')),
        role=_clean(details.get('@ccb_role')),
        slot_key=_clean(details.get('@ccb_slot')),
        project_id=_clean(details.get('@ccb_project_id')),
        managed_by=_clean(details.get('@ccb_managed_by')),
        namespace_epoch=_clean_int(details.get('@ccb_namespace_epoch')),
        alive=_pane_alive(details),
    )


def same_tmux_socket_path(left: str | None, right: str | None) -> bool:
    left_text = str(left or '').strip()
    right_text = str(right or '').strip()
    if not left_text or not right_text:
        return False
    try:
        return Path(left_text).expanduser().resolve() == Path(right_text).expanduser().resolve()
    except Exception:
        return left_text == right_text


def backend_socket_matches(backend, tmux_socket_path: str) -> bool:
    backend_socket_path = str(getattr(backend, '_socket_path', '') or '').strip()
    if not backend_socket_path:
        return False
    return same_tmux_socket_path(backend_socket_path, tmux_socket_path)


def _describe_pane_via_tmux(backend, pane_id: str) -> dict[str, str] | None:
    runner = getattr(backend, '_tmux_run', None)
    if not callable(runner):
        return None
    try:
        cp = runner(
            [
                'display-message',
                '-p',
                '-t',
                pane_id,
                '\t'.join(
                    (
                        '#{pane_id}',
                        '#{session_name}',
                        '#{window_id}',
                        '#{window_name}',
                        '#{pane_dead}',
                        '#{@ccb_role}',
                        '#{@ccb_slot}',
                        '#{@ccb_project_id}',
                        '#{@ccb_managed_by}',
                        '#{@ccb_namespace_epoch}',
                    )
                ),
            ],
            capture=True,
            check=False,
            timeout=0.5,
        )
    except Exception:
        return None
    if getattr(cp, 'returncode', 1) != 0:
        detail = tmux_failure_detail(
            cp,
            [
                'display-message',
                '-p',
                '-t',
                pane_id,
            ],
        )
        if is_tmux_transient_server_error_text(detail):
            raise TmuxTransientServerUnavailable(detail)
        return None
    line = ((getattr(cp, 'stdout', '') or '').splitlines() or [''])[0]
    return _decode_tmux_pane_description(line)


def _decode_tmux_pane_description(line: str) -> dict[str, str] | None:
    parts = line.split('\t')
    if len(parts) == 7:
        return {
            'pane_id': parts[0].strip(),
            'session_name': parts[1].strip(),
            'window_id': '',
            'window_name': '',
            'pane_dead': parts[2].strip(),
            '@ccb_role': parts[3].strip(),
            '@ccb_slot': parts[4].strip(),
            '@ccb_project_id': parts[5].strip(),
            '@ccb_managed_by': parts[6].strip(),
            '@ccb_namespace_epoch': '',
        }
    if len(parts) != 10:
        return None
    return {
        'pane_id': parts[0].strip(),
        'session_name': parts[1].strip(),
        'window_id': parts[2].strip(),
        'window_name': parts[3].strip(),
        'pane_dead': parts[4].strip(),
        '@ccb_role': parts[5].strip(),
        '@ccb_slot': parts[6].strip(),
        '@ccb_project_id': parts[7].strip(),
        '@ccb_managed_by': parts[8].strip(),
        '@ccb_namespace_epoch': parts[9].strip(),
    }


def _describe_pane_via_backend(backend, pane_id: str) -> dict[str, str] | None:
    descriptor = getattr(backend, 'describe_pane', None)
    if not callable(descriptor):
        return None
    try:
        described = descriptor(
            pane_id,
            user_options=('@ccb_role', '@ccb_slot', '@ccb_project_id', '@ccb_managed_by', '@ccb_namespace_epoch'),
        )
    except Exception:
        return None
    if not isinstance(described, dict):
        return None
    result = _stringify_details(described)
    if 'session_name' not in result:
        result['session_name'] = ''
    return result


def _stringify_details(described: dict[object, object]) -> dict[str, str]:
    return {str(key): str(value) for key, value in described.items()}


def _clean(value: object) -> str | None:
    text = str(value or '').strip()
    return text or None


def _clean_int(value: object) -> int | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _pane_alive(details: dict[str, str]) -> bool:
    return str(details.get('pane_dead') or '').strip() in {'', '0', 'false', 'False'}


__all__ = [
    'ProjectNamespacePaneRecord',
    'backend_socket_matches',
    'inspect_project_namespace_pane',
    'same_tmux_socket_path',
]
