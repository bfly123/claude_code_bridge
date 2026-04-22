from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import sys
from pathlib import Path


def _state_file() -> Path:
    root = Path(os.environ['CCB_FAKE_TMUX_STATE_DIR']).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root / 'fake-tmux-state.json'


def _load_state() -> dict:
    path = _state_file()
    if not path.exists():
        return {'servers': {}}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {'servers': {}}


def _save_state(state: dict) -> None:
    path = _state_file()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _server_key(socket_path: str | None, socket_name: str | None) -> str:
    if socket_path:
        canonical = _canonical_socket_path(socket_path)
        digest = hashlib.sha1(canonical.encode('utf-8')).hexdigest()[:16]
        return f'socket:{digest}'
    if socket_name:
        return f'name:{socket_name}'
    return 'default'


def _ensure_server(state: dict, key: str) -> dict:
    servers = state.setdefault('servers', {})
    server = servers.get(key)
    if isinstance(server, dict):
        return server
    server = {
        'next_pane': 1,
        'next_pid': 2000,
        'next_window': 1,
        'current_pane': '',
        'buffers': {},
        'sessions': {},
        'panes': {},
    }
    servers[key] = server
    return server


def _next_pane_id(server: dict) -> str:
    value = int(server.get('next_pane', 1) or 1)
    server['next_pane'] = value + 1
    return f'%{value}'


def _next_window_id(server: dict) -> str:
    value = int(server.get('next_window', 1) or 1)
    server['next_window'] = value + 1
    return f'@{value}'


def _next_pane_pid(server: dict) -> int:
    value = int(server.get('next_pid', 2000) or 2000)
    server['next_pid'] = value + 1
    return value


def _session(server: dict, name: str) -> dict | None:
    return (server.get('sessions') or {}).get(name)


def _window(server: dict, session_name: str, window_ref: str | None) -> dict | None:
    session = _session(server, session_name)
    if session is None:
        return None
    windows = session.get('windows') or {}
    if not window_ref:
        active = str(session.get('active_window') or '').strip()
        if active:
            return windows.get(active)
        if windows:
            first_id = next(iter(windows.keys()))
            return windows.get(first_id)
        return None
    for window_id, window in windows.items():
        if window_ref in {window_id, str(window.get('name') or '').strip()}:
            return window
    return None


def _pane(server: dict, pane_id: str) -> dict | None:
    return (server.get('panes') or {}).get(pane_id)


def _pane_from_target(server: dict, target: str | None) -> dict | None:
    text = str(target or '').strip()
    if not text:
        current = str(server.get('current_pane') or '').strip()
        return _pane(server, current)
    if text.startswith('%'):
        return _pane(server, text)
    if ':' in text:
        session_name, window_ref = text.split(':', 1)
        window = _window(server, session_name, window_ref)
    else:
        window = _window(server, text, None)
    if window is None:
        return None
    panes = list(window.get('panes', []) or [])
    if not panes:
        return None
    return _pane(server, str(panes[0]))


def _resolve_target(server: dict, target: str | None) -> tuple[dict | None, dict | None, dict | None]:
    pane = _pane_from_target(server, target)
    if pane is None:
        return None, None, None
    session = _session(server, str(pane.get('session') or ''))
    window = _window(server, str(pane.get('session') or ''), str(pane.get('window_id') or ''))
    return pane, window, session


def _render(format_string: str, *, pane: dict | None, window: dict | None, session: dict | None) -> str:
    user_options = dict((pane or {}).get('user_options', {}) or {})
    styles = dict((pane or {}).get('styles', {}) or {})
    pane_active = '1' if str((pane or {}).get('id') or '') == str(((pane or {}).get('_current_pane') or '')).strip() else '0'
    mapping = {
        'pane_id': str((pane or {}).get('id') or ''),
        'pane_pid': str((pane or {}).get('pane_pid') or ''),
        'pane_active': pane_active,
        'pane_title': str((pane or {}).get('title') or ''),
        'pane_dead': '1' if bool((pane or {}).get('dead')) else '0',
        'pane_width': str((pane or {}).get('width') or 160),
        'pane_height': str((pane or {}).get('height') or 48),
        'pane_in_mode': '0',
        'pane_pipe': '1' if bool((pane or {}).get('pipe')) else '0',
        'pane_tty': str((pane or {}).get('tty') or ''),
        'session_name': str((session or {}).get('name') or ''),
        'window_id': str((window or {}).get('id') or ''),
        'window_name': str((window or {}).get('name') or ''),
        'window_active': '1' if bool((window or {}).get('active')) else '0',
        'window_zoomed_flag': '0',
        'client_tty': '',
        **user_options,
        **styles,
    }
    format_string = format_string.replace(
        '#{?pane_active,#{pane_id},}',
        mapping['pane_id'] if pane_active == '1' else '',
    )

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(mapping.get(key, ''))

    return re.sub(r'#\{([^}]+)\}', _replace, format_string)


def _append_pane_text(server: dict, pane_id: str, text: str) -> None:
    pane = _pane(server, pane_id)
    if pane is None:
        return
    pane['content'] = f"{pane.get('content', '')}{text}"
    log_path = str(pane.get('log_path') or '').strip()
    if log_path:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(pane.get('content') or ''), encoding='utf-8')


def _parse_global_args(argv: list[str]) -> tuple[str | None, str | None, list[str]]:
    socket_path = None
    socket_name = None
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == '-S' and index + 1 < len(argv):
            socket_path = argv[index + 1]
            index += 2
            continue
        if item == '-L' and index + 1 < len(argv):
            socket_name = argv[index + 1]
            index += 2
            continue
        break
    return socket_path, socket_name, argv[index:]


def _canonical_socket_path(socket_path: str) -> str:
    text = str(socket_path or '').strip().strip('"')
    if not text:
        return ''
    expanded = str(Path(text).expanduser())
    normalized = os.path.normpath(os.path.abspath(expanded))
    if os.name != 'nt':
        return normalized
    return os.path.normcase(_expand_windows_existing_ancestor(normalized))


def _expand_windows_existing_ancestor(path_text: str) -> str:
    candidate = Path(path_text)
    suffix: list[str] = []
    while True:
        if candidate.exists():
            break
        parent = candidate.parent
        if parent == candidate:
            return path_text
        suffix.insert(0, candidate.name)
        candidate = parent
    long_base = _windows_long_path(str(candidate))
    if not long_base:
        return path_text
    if suffix:
        return os.path.join(long_base, *suffix)
    return long_base


def _windows_long_path(path_text: str) -> str:
    if os.name != 'nt':
        return path_text
    try:
        buffer_size = 32768
        buffer = ctypes.create_unicode_buffer(buffer_size)
        result = ctypes.windll.kernel32.GetLongPathNameW(str(path_text), buffer, buffer_size)
        if result:
            return buffer.value
    except Exception:
        pass
    return path_text


def _arg_value(args: list[str], flag: str, default: str = '') -> str:
    if flag not in args:
        return default
    index = args.index(flag)
    if index + 1 >= len(args):
        return default
    return args[index + 1]


def _set_active_window(server: dict, session_name: str, window_id: str) -> None:
    session = _session(server, session_name)
    if session is None:
        return
    session['active_window'] = window_id
    for current_id, window in (session.get('windows') or {}).items():
        window['active'] = current_id == window_id


def _create_session(server: dict, args: list[str]) -> int:
    name = _arg_value(args, '-s')
    if not name:
        return 1
    window_name = _arg_value(args, '-n', '0') or '0'
    sessions = server.setdefault('sessions', {})
    if name in sessions:
        return 0
    pane_id = _next_pane_id(server)
    window_id = _next_window_id(server)
    window = {'id': window_id, 'name': window_name, 'active': True, 'panes': [pane_id]}
    session = {'name': name, 'active_window': window_id, 'windows': {window_id: window}}
    pane = {
        'id': pane_id,
        'pane_pid': _next_pane_pid(server),
        'session': name,
        'window_id': window_id,
        'title': '',
        'dead': False,
        'pipe': False,
        'tty': f'tty-{pane_id[1:]}',
        'content': '',
        'user_options': {},
        'styles': {},
        'width': 160,
        'height': 48,
    }
    sessions[name] = session
    server.setdefault('panes', {})[pane_id] = pane
    server['current_pane'] = pane_id
    return 0


def _new_window(server: dict, args: list[str]) -> int:
    session_name = _arg_value(args, '-t')
    session = _session(server, session_name)
    if session is None:
        return 1
    window_name = _arg_value(args, '-n', '')
    if not window_name:
        return 1
    window_id = _next_window_id(server)
    pane_id = _next_pane_id(server)
    window = {'id': window_id, 'name': window_name, 'active': False, 'panes': [pane_id]}
    session['windows'][window_id] = window
    pane = {
        'id': pane_id,
        'pane_pid': _next_pane_pid(server),
        'session': session_name,
        'window_id': window_id,
        'title': '',
        'dead': False,
        'pipe': False,
        'tty': f'tty-{pane_id[1:]}',
        'content': '',
        'user_options': {},
        'styles': {},
        'width': 160,
        'height': 48,
    }
    server.setdefault('panes', {})[pane_id] = pane
    return 0


def _list_panes(server: dict, args: list[str]) -> tuple[int, str]:
    fmt = _arg_value(args, '-F', '#{pane_id}')
    target = _arg_value(args, '-t')
    include_all = '-a' in args
    panes: list[dict] = []
    if include_all:
        panes = list(dict(server.get('panes', {})).values())
    else:
        pane = _pane_from_target(server, target)
        if pane is None:
            return 1, ''
        session = _session(server, str(pane.get('session') or ''))
        window = _window(server, str(pane.get('session') or ''), str(pane.get('window_id') or ''))
        if session is None or window is None:
            return 1, ''
        panes = [_pane(server, pane_id) for pane_id in list(window.get('panes', []))]
        panes = [item for item in panes if item is not None]
    lines: list[str] = []
    for pane in panes:
        session = _session(server, str(pane.get('session') or ''))
        window = _window(server, str(pane.get('session') or ''), str(pane.get('window_id') or ''))
        pane_view = dict(pane)
        pane_view['_current_pane'] = str(server.get('current_pane') or '')
        lines.append(_render(fmt, pane=pane_view, window=window, session=session))
    return 0, '\n'.join(lines)


def _display_message(server: dict, args: list[str]) -> tuple[int, str]:
    target = _arg_value(args, '-t')
    format_string = args[-1] if args else ''
    pane, window, session = _resolve_target(server, target)
    if str(target or '').strip() and pane is None:
        return 1, ''
    pane_view = dict(pane) if pane is not None else None
    if pane_view is not None:
        pane_view['_current_pane'] = str(server.get('current_pane') or '')
    return 0, _render(format_string, pane=pane_view, window=window, session=session)


def _split_window(server: dict, args: list[str]) -> tuple[int, str]:
    target = _arg_value(args, '-t')
    pane = _pane(server, target)
    if pane is None:
        return 1, ''
    pane_id = _next_pane_id(server)
    new_pane = {
        'id': pane_id,
        'pane_pid': _next_pane_pid(server),
        'session': str(pane.get('session') or ''),
        'window_id': str(pane.get('window_id') or ''),
        'title': '',
        'dead': False,
        'pipe': False,
        'tty': f'tty-{pane_id[1:]}',
        'content': '',
        'user_options': {},
        'styles': {},
        'width': 80,
        'height': 48,
    }
    server.setdefault('panes', {})[pane_id] = new_pane
    window = _window(server, str(new_pane.get('session') or ''), str(new_pane.get('window_id') or ''))
    if window is None:
        return 1, ''
    panes = list(window.get('panes', []) or [])
    panes.append(pane_id)
    window['panes'] = panes
    server['current_pane'] = pane_id
    return 0, pane_id


def _select_pane(server: dict, args: list[str]) -> int:
    target = _arg_value(args, '-t')
    pane = _pane(server, target)
    if pane is None:
        return 1
    if '-T' in args:
        pane['title'] = _arg_value(args, '-T')
    server['current_pane'] = target
    return 0


def _set_option(server: dict, args: list[str]) -> int:
    tail = list(args)
    if '-t' in tail:
        index = tail.index('-t')
        tail = tail[:index] + tail[index + 2:]
    option_args = [item for item in tail if item not in {'set-option', '-p', '-g'}]
    if len(option_args) < 2:
        return 0
    option_name = option_args[0]
    option_value = option_args[1]
    if '-p' not in args:
        target = _arg_value(args, '-t')
        if '-g' in args:
            server.setdefault('global_options', {})[option_name] = option_value
            return 0
        session_name = target.split(':', 1)[0] if target else ''
        session = _session(server, session_name)
        if session is None:
            return 1
        session.setdefault('options', {})[option_name] = option_value
        return 0
    target = _arg_value(args, '-t')
    pane = _pane(server, target)
    if pane is None:
        return 1
    if option_name.startswith('@'):
        pane.setdefault('user_options', {})[option_name] = option_value
    else:
        pane.setdefault('styles', {})[option_name] = option_value
    return 0


def _set_window_option(server: dict, args: list[str]) -> int:
    target = _arg_value(args, '-t')
    option_args = [item for item in args if item not in {'set-window-option'}]
    if '-t' in option_args:
        index = option_args.index('-t')
        option_args = option_args[:index] + option_args[index + 2:]
    if len(option_args) < 2:
        return 0
    if ':' in target:
        session_name, window_ref = target.split(':', 1)
    else:
        session_name, window_ref = target, None
    window = _window(server, session_name, window_ref)
    if window is None:
        return 1
    window.setdefault('options', {})[option_args[0]] = option_args[1]
    return 0


def _set_hook(server: dict, args: list[str]) -> int:
    target = _arg_value(args, '-t')
    hook_args = [item for item in args if item not in {'set-hook'}]
    if '-t' in hook_args:
        index = hook_args.index('-t')
        hook_args = hook_args[:index] + hook_args[index + 2:]
    if len(hook_args) < 2:
        return 0
    session = _session(server, target)
    if session is None:
        return 1
    session.setdefault('hooks', {})[hook_args[0]] = hook_args[1]
    return 0


def _has_session(server: dict, args: list[str]) -> int:
    target = _arg_value(args, '-t')
    if not target:
        return 1
    session_name = target.split(':', 1)[0]
    return 0 if _session(server, session_name) is not None else 1


def _capture_pane(server: dict, args: list[str]) -> tuple[int, str]:
    target = _arg_value(args, '-t')
    pane = _pane(server, target)
    if pane is None:
        return 1, ''
    content = str(pane.get('content') or '')
    return 0, content.rstrip('\n')


def _respawn_pane(server: dict, args: list[str]) -> int:
    target = _arg_value(args, '-t')
    pane = _pane(server, target)
    if pane is None:
        return 1
    pane['dead'] = False
    pane['pane_pid'] = _next_pane_pid(server)
    pane['respawned'] = True
    pane['cwd'] = _arg_value(args, '-c')
    if '--' in args:
        index = args.index('--')
        pane['last_command'] = ' '.join(args[index + 1:])
    elif args:
        pane['last_command'] = args[-1]
    return 0


def _pipe_pane(server: dict, args: list[str]) -> int:
    target = _arg_value(args, '-t')
    pane = _pane(server, target)
    if pane is None:
        return 1
    pane['pipe'] = True
    command = args[-1] if args else ''
    match = re.search(r'tee\\s+-a\\s+(.+)$', command)
    if match:
        pane['log_path'] = match.group(1).strip().strip('\"')
        path = Path(str(pane['log_path']))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
    return 0


def _kill_pane(server: dict, args: list[str]) -> int:
    target = _arg_value(args, '-t')
    pane = _pane(server, target)
    if pane is None:
        return 1
    pane['dead'] = True
    return 0


def _kill_session(server: dict, args: list[str]) -> int:
    target = _arg_value(args, '-t')
    if not target:
        return 1
    session_name = target.split(':', 1)[0]
    session = _session(server, session_name)
    if session is None:
        return 1
    for window in (session.get('windows') or {}).values():
        for pane_id in list(window.get('panes', []) or []):
            (server.get('panes') or {}).pop(str(pane_id), None)
    (server.get('sessions') or {}).pop(session_name, None)
    if str(server.get('current_pane') or '').startswith('%') and _pane(server, str(server.get('current_pane') or '')) is None:
        server['current_pane'] = ''
    return 0


def _list_windows(server: dict, args: list[str]) -> tuple[int, str]:
    session_name = _arg_value(args, '-t')
    session = _session(server, session_name)
    if session is None:
        return 1, ''
    fmt = _arg_value(args, '-F', '#{window_id}\t#{window_name}\t#{window_active}')
    lines: list[str] = []
    for window in (session.get('windows') or {}).values():
        pane = _pane_from_target(server, f"{session_name}:{window.get('id')}")
        lines.append(_render(fmt, pane=pane, window=window, session=session))
    return 0, '\n'.join(lines)


def _select_window(server: dict, args: list[str]) -> int:
    target = _arg_value(args, '-t')
    if ':' not in target:
        return 1
    session_name, window_ref = target.split(':', 1)
    window = _window(server, session_name, window_ref)
    if window is None:
        return 1
    _set_active_window(server, session_name, str(window.get('id') or ''))
    panes = list(window.get('panes', []) or [])
    if panes:
        server['current_pane'] = str(panes[0])
    return 0


def _rename_window(server: dict, args: list[str]) -> int:
    target = _arg_value(args, '-t')
    if ':' not in target or not args:
        return 1
    new_name = args[-1]
    session_name, window_ref = target.split(':', 1)
    window = _window(server, session_name, window_ref)
    if window is None:
        return 1
    window['name'] = new_name
    return 0


def _kill_window(server: dict, args: list[str]) -> int:
    target = _arg_value(args, '-t')
    if ':' not in target:
        return 1
    session_name, window_ref = target.split(':', 1)
    session = _session(server, session_name)
    window = _window(server, session_name, window_ref)
    if session is None or window is None:
        return 1
    for pane_id in list(window.get('panes', []) or []):
        (server.get('panes') or {}).pop(str(pane_id), None)
    (session.get('windows') or {}).pop(str(window.get('id') or ''), None)
    if str(session.get('active_window') or '') == str(window.get('id') or ''):
        remaining = list((session.get('windows') or {}).keys())
        session['active_window'] = remaining[0] if remaining else ''
        for current_id, current in (session.get('windows') or {}).items():
            current['active'] = current_id == session['active_window']
    return 0


def _load_buffer(server: dict, args: list[str]) -> int:
    name = _arg_value(args, '-b')
    if not name:
        return 1
    text = sys.stdin.buffer.read().decode('utf-8', errors='replace')
    server.setdefault('buffers', {})[name] = text
    return 0


def _paste_buffer(server: dict, args: list[str]) -> int:
    name = _arg_value(args, '-b')
    target = _arg_value(args, '-t')
    text = str((server.get('buffers') or {}).get(name, ''))
    pane = _pane_from_target(server, target)
    if pane is None:
        return 1
    _append_pane_text(server, str(pane.get('id') or ''), text)
    return 0


def _delete_buffer(server: dict, args: list[str]) -> int:
    name = _arg_value(args, '-b')
    (server.get('buffers') or {}).pop(name, None)
    return 0


def _send_keys(server: dict, args: list[str]) -> int:
    target = _arg_value(args, '-t')
    pane = _pane_from_target(server, target)
    if pane is None:
        return 1
    if '-X' in args:
        return 0
    if '-l' in args:
        text = _arg_value(args, '-l')
        _append_pane_text(server, str(pane.get('id') or ''), text)
        return 0
    key = args[-1] if args else ''
    if key == 'Enter':
        _append_pane_text(server, str(pane.get('id') or ''), '\n')
    return 0


def _show_option(args: list[str]) -> tuple[int, str]:
    if args[-1:] == ['default-shell']:
        return 0, ''
    return 0, ''


def _list_sessions(server: dict, args: list[str]) -> tuple[int, str]:
    fmt = _arg_value(args, '-F', '#{session_name}')
    lines = []
    for session in dict(server.get('sessions', {})).values():
        lines.append(_render(fmt, pane=None, window=None, session=session))
    return 0, '\n'.join(lines)


def _run_command(server: dict, args: list[str]) -> tuple[int, str]:
    if not args:
        return 0, ''
    command = args[0]
    if command == 'start-server':
        return 0, ''
    if command == 'set-option':
        return _set_option(server, args), ''
    if command == 'set-window-option':
        return _set_window_option(server, args), ''
    if command == 'set-hook':
        return _set_hook(server, args), ''
    if command == 'show-option':
        return _show_option(args)
    if command == 'new-session':
        return _create_session(server, args), ''
    if command == 'new-window':
        return _new_window(server, args), ''
    if command == 'list-panes':
        return _list_panes(server, args)
    if command == 'display-message':
        return _display_message(server, args)
    if command == 'split-window':
        return _split_window(server, args)
    if command == 'select-pane':
        return _select_pane(server, args), ''
    if command == 'has-session':
        return _has_session(server, args), ''
    if command == 'capture-pane':
        return _capture_pane(server, args)
    if command == 'respawn-pane':
        return _respawn_pane(server, args), ''
    if command == 'pipe-pane':
        return _pipe_pane(server, args), ''
    if command == 'kill-pane':
        return _kill_pane(server, args), ''
    if command == 'kill-session':
        return _kill_session(server, args), ''
    if command == 'list-windows':
        return _list_windows(server, args)
    if command == 'select-window':
        return _select_window(server, args), ''
    if command == 'rename-window':
        return _rename_window(server, args), ''
    if command == 'kill-window':
        return _kill_window(server, args), ''
    if command == 'load-buffer':
        return _load_buffer(server, args), ''
    if command == 'paste-buffer':
        return _paste_buffer(server, args), ''
    if command == 'delete-buffer':
        return _delete_buffer(server, args), ''
    if command == 'send-keys':
        return _send_keys(server, args), ''
    if command in {'attach-session', 'attach', 'resize-pane'}:
        return 0, ''
    if command == 'kill-server':
        server['sessions'] = {}
        server['panes'] = {}
        server['buffers'] = {}
        server['current_pane'] = ''
        return 0, ''
    if command == 'list-sessions':
        return _list_sessions(server, args)
    return 0, ''


def main(argv: list[str]) -> int:
    socket_path, socket_name, command_args = _parse_global_args(argv)
    key = _server_key(socket_path, socket_name)
    state = _load_state()
    server = _ensure_server(state, key)
    code, stdout = _run_command(server, command_args)
    _save_state(state)
    if stdout:
        sys.stdout.write(stdout)
        if not stdout.endswith('\n'):
            sys.stdout.write('\n')
    return int(code)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
