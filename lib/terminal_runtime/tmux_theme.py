from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import shlex
from typing import Mapping


@dataclass(frozen=True)
class TmuxPaneVisual:
    label_style: str
    border_style: str
    active_border_style: str


@dataclass(frozen=True)
class TmuxThemeProfile:
    name: str
    fallback_label_style: str
    pane_border_style: str
    pane_active_border_style: str
    window_style: str | None = None
    window_active_style: str | None = None


@dataclass(frozen=True)
class RenderedTmuxSessionTheme:
    profile_name: str
    session_options: dict[str, str]
    window_options: dict[str, str]


_DEFAULT_FALLBACK_LABEL_STYLE = '#[fg=#1e1e2e]#[bg=#7aa2f7]#[bold]'

_THEME_PROFILES: dict[str, TmuxThemeProfile] = {
    'default': TmuxThemeProfile(
        name='default',
        fallback_label_style=_DEFAULT_FALLBACK_LABEL_STYLE,
        pane_border_style='fg=#3b4261,bold',
        pane_active_border_style='fg=#7aa2f7,bold',
    ),
    'contrast': TmuxThemeProfile(
        name='contrast',
        fallback_label_style=_DEFAULT_FALLBACK_LABEL_STYLE,
        pane_border_style='fg=#565f89,bold',
        pane_active_border_style='fg=#89b4fa,bold',
        window_style='bg=#181825',
        window_active_style='bg=#1e1e2e',
    ),
}

_CONTRAST_TERMINAL_FAMILIES = {'apple_terminal'}

_STATUS_STYLE = 'bg=#1e1e2e fg=#cdd6f4'
_STATUS_FORMAT_1 = '#[align=centre,bg=#1e1e2e,fg=#6c7086]Copy: MouseDrag  Paste: Shift-Ctrl-v  Focus: Ctrl-b o'
_STATUS_FORMAT_0 = '#[align=left bg=#1e1e2e]#{T:status-left}#[align=centre fg=#6c7086]#{b:pane_current_path}#[align=right]#{T:status-right}'
_WINDOW_STATUS_FORMAT = ''
_WINDOW_STATUS_CURRENT_FORMAT = ''
_WINDOW_STATUS_SEPARATOR = ''
_PANE_BORDER_STATUS = 'top'


def _visual(*, bg: str, border: str | None = None, active: str | None = None, fg: str = '#16161e') -> TmuxPaneVisual:
    border_color = str(border or bg).strip()
    active_color = str(active or border_color).strip()
    return TmuxPaneVisual(
        label_style=f'#[fg={fg}]#[bg={bg}]#[bold]',
        border_style=f'fg={border_color}',
        active_border_style=f'fg={active_color},bold',
    )


_CMD_VISUALS_DEFAULT: tuple[TmuxPaneVisual, ...] = (
    _visual(bg='#7dcfff', border='#5fb3d6', active='#7dcfff'),
    _visual(bg='#73daca', border='#4fb7a9', active='#73daca'),
    _visual(bg='#89b4fa', border='#6b8fd6', active='#89b4fa'),
    _visual(bg='#2ac3de', border='#1b9fb8', active='#2ac3de'),
)

_AGENT_VISUALS_DEFAULT: tuple[TmuxPaneVisual, ...] = (
    _visual(bg='#ff9e64', border='#d9824f', active='#ff9e64'),
    _visual(bg='#9ece6a', border='#7ca952', active='#9ece6a'),
    _visual(bg='#f7768e', border='#d85f78', active='#f7768e'),
    _visual(bg='#e0af68', border='#bd8d4f', active='#e0af68'),
    _visual(bg='#bb9af7', border='#9d7fda', active='#bb9af7'),
    _visual(bg='#73daca', border='#54bda7', active='#73daca'),
    _visual(bg='#7aa2f7', border='#5d82d6', active='#7aa2f7'),
    _visual(bg='#f6bd60', border='#d69f46', active='#f6bd60'),
    _visual(bg='#ff757f', border='#da5a66', active='#ff757f'),
    _visual(bg='#8bd5ca', border='#68b6aa', active='#8bd5ca'),
    _visual(bg='#c6a0f6', border='#a885d8', active='#c6a0f6'),
    _visual(bg='#a6da95', border='#84b777', active='#a6da95'),
    TmuxPaneVisual(
        label_style='#[fg=#16161e]#[bg=#f5bde6]#[bold]',
        border_style='fg=#d49ac5',
        active_border_style='fg=#f5bde6,bold',
    ),
)

_CMD_VISUALS_CONTRAST: tuple[TmuxPaneVisual, ...] = (
    _visual(bg='#7dcfff'),
    _visual(bg='#73daca'),
    _visual(bg='#89b4fa'),
    _visual(bg='#2ac3de'),
)

_AGENT_VISUALS_CONTRAST: tuple[TmuxPaneVisual, ...] = (
    _visual(bg='#ff9e64'),
    _visual(bg='#9ece6a'),
    _visual(bg='#f7768e'),
    _visual(bg='#e0af68'),
    _visual(bg='#bb9af7'),
    _visual(bg='#73daca'),
    _visual(bg='#7aa2f7'),
    _visual(bg='#f6bd60'),
    _visual(bg='#ff757f'),
    _visual(bg='#8bd5ca'),
    _visual(bg='#c6a0f6'),
    _visual(bg='#a6da95'),
    _visual(bg='#f5bde6'),
)


def _env(environ: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return environ if environ is not None else os.environ


def detect_terminal_family(environ: Mapping[str, str] | None = None) -> str:
    env = _env(environ)
    for key in ('TERM_PROGRAM', 'LC_TERMINAL'):
        value = str(env.get(key, '') or '').strip().lower()
        if value:
            return value
    return str(env.get('TERM', '') or '').strip().lower()


def _normalize_profile_name(value: str | None) -> str | None:
    name = str(value or '').strip().lower()
    if not name:
        return None
    return name if name in _THEME_PROFILES else None


def tmux_theme_profile(environ: Mapping[str, str] | None = None) -> str:
    env = _env(environ)
    override = _normalize_profile_name(env.get('CCB_TMUX_THEME_PROFILE'))
    if override is not None:
        return override
    family = detect_terminal_family(env)
    return 'contrast' if family in _CONTRAST_TERMINAL_FAMILIES else 'default'


def tmux_status_interval(environ: Mapping[str, str] | None = None) -> str:
    raw = str(_env(environ).get('CCB_TMUX_STATUS_INTERVAL', '') or '').strip()
    if raw.isdigit() and int(raw) > 0:
        return str(int(raw))
    return '5'


def theme_profile_definition(profile_name: str | None = None, *, environ: Mapping[str, str] | None = None) -> TmuxThemeProfile:
    resolved = _normalize_profile_name(profile_name) or tmux_theme_profile(environ)
    return _THEME_PROFILES.get(resolved, _THEME_PROFILES['default'])


def pane_border_format(profile_name: str | None = None, *, environ: Mapping[str, str] | None = None) -> str:
    profile = theme_profile_definition(profile_name, environ=environ)
    return (
        '#{?#{@ccb_agent},'
        f'#{{?#{{@ccb_label_style}},#{{@ccb_label_style}},{profile.fallback_label_style}}} '
        '#{@ccb_agent} #[default],'
        '#[fg=#565f89] #{pane_title} #[default]}'
    )


def render_tmux_session_theme(
    *,
    ccb_version: str,
    status_script: str | None,
    git_script: str | None,
    environ: Mapping[str, str] | None = None,
    profile_name: str | None = None,
) -> RenderedTmuxSessionTheme:
    profile = theme_profile_definition(profile_name, environ=environ)
    normalized_version = _normalized_ccb_version(ccb_version)
    focus_agent = '#{?#{@ccb_agent},#{@ccb_agent},-}'
    accent = '#{?client_prefix,#f38ba8,#{?pane_in_mode,#fab387,#f5c2e7}}'
    label = '#{?client_prefix,KEY,#{?pane_in_mode,COPY,INPUT}}'
    git_info = f'#({git_script} "#{{pane_current_path}}")' if git_script else '-'
    status_indicator = f'#({status_script} modern "#{{pane_current_path}}")' if status_script else '-'

    session_options = {
        '@ccb_active': '1',
        '@ccb_version': normalized_version,
        '@ccb_theme_profile': profile.name,
        'status-position': 'bottom',
        'status-interval': tmux_status_interval(environ),
        'status-style': _STATUS_STYLE,
        'status': '2',
        'status-left-length': '80',
        'status-right-length': '120',
        'status-format[1]': _STATUS_FORMAT_1,
        'status-format[0]': _STATUS_FORMAT_0,
        'status-left': (
            f'#[fg=#1e1e2e,bg={accent},bold] {label} '
            f'#[fg={accent},bg=#cba6f7]#[fg=#1e1e2e,bg=#cba6f7] {git_info} '
            '#[fg=#cba6f7,bg=#1e1e2e]'
        ),
        'status-right': (
            f'#[fg=#f38ba8,bg=#1e1e2e]#[fg=#1e1e2e,bg=#f38ba8,bold] {focus_agent} '
            f'#[fg=#cba6f7,bg=#f38ba8]#[fg=#1e1e2e,bg=#cba6f7,bold] CCB:{normalized_version} '
            f'#[fg=#89b4fa,bg=#cba6f7]#[fg=#cdd6f4,bg=#89b4fa] {status_indicator} '
            '#[fg=#fab387,bg=#89b4fa]#[fg=#1e1e2e,bg=#fab387,bold] %m/%d %a %H:%M #[default]'
        ),
        'window-status-format': _WINDOW_STATUS_FORMAT,
        'window-status-current-format': _WINDOW_STATUS_CURRENT_FORMAT,
        'window-status-separator': _WINDOW_STATUS_SEPARATOR,
    }
    window_options = {
        'pane-border-status': _PANE_BORDER_STATUS,
        'pane-border-style': profile.pane_border_style,
        'pane-active-border-style': profile.pane_active_border_style,
        'pane-border-format': pane_border_format(profile.name),
    }
    if profile.window_style:
        window_options['window-style'] = profile.window_style
    if profile.window_active_style:
        window_options['window-active-style'] = profile.window_active_style
    return RenderedTmuxSessionTheme(
        profile_name=profile.name,
        session_options=session_options,
        window_options=window_options,
    )


def _pane_palette(*, profile_name: str, is_cmd: bool) -> tuple[TmuxPaneVisual, ...]:
    if profile_name == 'contrast':
        return _CMD_VISUALS_CONTRAST if is_cmd else _AGENT_VISUALS_CONTRAST
    return _CMD_VISUALS_DEFAULT if is_cmd else _AGENT_VISUALS_DEFAULT


def pane_visual(
    *,
    project_id: str | None = None,
    slot_key: str | None = None,
    order_index: int | None = None,
    is_cmd: bool = False,
    profile_name: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> TmuxPaneVisual:
    resolved_profile = theme_profile_definition(profile_name, environ=environ).name
    visuals = _pane_palette(profile_name=resolved_profile, is_cmd=is_cmd)
    return _select_visual(visuals, project_id=project_id, slot_key=slot_key, fallback_index=order_index)


def _select_visual(
    visuals: tuple[TmuxPaneVisual, ...],
    *,
    project_id: str | None,
    slot_key: str | None,
    fallback_index: int | None,
) -> TmuxPaneVisual:
    if project_id and slot_key:
        key = f'{project_id}:{slot_key}'
        return visuals[_stable_index(key, len(visuals))]
    index = max(0, int(fallback_index or 0))
    return visuals[index % len(visuals)]


def _stable_index(key: str, size: int) -> int:
    if size <= 0:
        return 0
    digest = hashlib.sha256(str(key or '').encode('utf-8')).hexdigest()
    return int(digest[:8], 16) % size


def shell_exports(
    *,
    ccb_version: str,
    status_script: str | None,
    git_script: str | None,
    environ: Mapping[str, str] | None = None,
    profile_name: str | None = None,
) -> str:
    rendered = render_tmux_session_theme(
        ccb_version=ccb_version,
        status_script=status_script,
        git_script=git_script,
        environ=environ,
        profile_name=profile_name,
    )
    items = {
        'CCB_TMUX_RENDERED_THEME_PROFILE': rendered.profile_name,
        'CCB_TMUX_RENDERED_STATUS_POSITION': rendered.session_options['status-position'],
        'CCB_TMUX_RENDERED_STATUS_INTERVAL': rendered.session_options['status-interval'],
        'CCB_TMUX_RENDERED_STATUS_STYLE': rendered.session_options['status-style'],
        'CCB_TMUX_RENDERED_STATUS_LINES': rendered.session_options['status'],
        'CCB_TMUX_RENDERED_STATUS_LEFT_LENGTH': rendered.session_options['status-left-length'],
        'CCB_TMUX_RENDERED_STATUS_RIGHT_LENGTH': rendered.session_options['status-right-length'],
        'CCB_TMUX_RENDERED_STATUS_FORMAT_0': rendered.session_options['status-format[0]'],
        'CCB_TMUX_RENDERED_STATUS_FORMAT_1': rendered.session_options['status-format[1]'],
        'CCB_TMUX_RENDERED_STATUS_LEFT': rendered.session_options['status-left'],
        'CCB_TMUX_RENDERED_STATUS_RIGHT': rendered.session_options['status-right'],
        'CCB_TMUX_RENDERED_WINDOW_STATUS_FORMAT': rendered.session_options['window-status-format'],
        'CCB_TMUX_RENDERED_WINDOW_STATUS_CURRENT_FORMAT': rendered.session_options['window-status-current-format'],
        'CCB_TMUX_RENDERED_WINDOW_STATUS_SEPARATOR': rendered.session_options['window-status-separator'],
        'CCB_TMUX_RENDERED_PANE_BORDER_STATUS': rendered.window_options['pane-border-status'],
        'CCB_TMUX_RENDERED_PANE_BORDER_STYLE': rendered.window_options['pane-border-style'],
        'CCB_TMUX_RENDERED_PANE_ACTIVE_BORDER_STYLE': rendered.window_options['pane-active-border-style'],
        'CCB_TMUX_RENDERED_PANE_BORDER_FORMAT': rendered.window_options['pane-border-format'],
        'CCB_TMUX_RENDERED_WINDOW_STYLE': rendered.window_options.get('window-style', ''),
        'CCB_TMUX_RENDERED_WINDOW_ACTIVE_STYLE': rendered.window_options.get('window-active-style', ''),
    }
    return '\n'.join(f'{key}={shlex.quote(value)}' for key, value in items.items())


def _normalized_ccb_version(value: str) -> str:
    return str(value or '?').strip() or '?'


__all__ = [
    'RenderedTmuxSessionTheme',
    'TmuxPaneVisual',
    'TmuxThemeProfile',
    'detect_terminal_family',
    'pane_border_format',
    'pane_visual',
    'render_tmux_session_theme',
    'shell_exports',
    'theme_profile_definition',
    'tmux_status_interval',
    'tmux_theme_profile',
]
