from __future__ import annotations

import subprocess

from terminal_runtime.tmux_panes import TmuxPaneService


def _cp(*, stdout: str = '', returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=['tmux'], returncode=returncode, stdout=stdout, stderr='')


def test_tmux_pane_service_gets_current_pane_and_finds_marker() -> None:
    calls: list[list[str]] = []

    def tmux_run(args, **kwargs):
        calls.append(args)
        if args == ['display-message', '-p', '-t', '%1', '#{pane_id}']:
            return _cp(stdout='%1\n')
        if args == ['list-panes', '-a', '-F', '#{pane_id}\t#{pane_title}']:
            return _cp(stdout='%1\tCCB-one\n%2\tOTHER\n')
        return _cp(stdout='%1\n')

    service = TmuxPaneService(
        tmux_run_fn=tmux_run,
        looks_like_pane_id_fn=lambda value: value.startswith('%'),
        normalize_split_direction_fn=lambda direction: ('-h', 'right'),
        pane_exists_output_fn=lambda output: output.strip().startswith('%'),
        pane_id_by_title_marker_output_fn=lambda text, marker: '%1' if marker == 'CCB' else None,
        pane_is_alive_fn=lambda output: output.strip() == '0',
        normalize_user_option_fn=lambda name: '@' + name.strip('@'),
        strip_ansi_fn=lambda text: text.replace('\x1b[31m', '').replace('\x1b[0m', ''),
    )

    assert service.get_current_pane_id(env_pane='%1') == '%1'
    assert service.find_pane_by_title_marker('CCB') == '%1'


def test_tmux_pane_service_sets_user_option_and_reads_content() -> None:
    calls: list[list[str]] = []

    def tmux_run(args, **kwargs):
        calls.append(args)
        if args[:2] == ['capture-pane', '-t']:
            return _cp(stdout='\x1b[31mhello\x1b[0m\n')
        if args[:2] == ['display-message', '-p'] and '#{pane_dead}' in args:
            return _cp(stdout='0\n')
        return _cp()

    service = TmuxPaneService(
        tmux_run_fn=tmux_run,
        looks_like_pane_id_fn=lambda value: value.startswith('%'),
        normalize_split_direction_fn=lambda direction: ('-h', 'right'),
        pane_exists_output_fn=lambda output: output.strip().startswith('%'),
        pane_id_by_title_marker_output_fn=lambda text, marker: None,
        pane_is_alive_fn=lambda output: output.strip() == '0',
        normalize_user_option_fn=lambda name: '@' + name.strip('@'),
        strip_ansi_fn=lambda text: text.replace('\x1b[31m', '').replace('\x1b[0m', ''),
    )

    service.set_pane_user_option('%3', 'ccb_agent', 'Gemini')
    text = service.get_pane_content('%3', lines=20)
    alive = service.is_pane_alive('%3')

    assert calls[0] == ['set-option', '-p', '-t', '%3', '@ccb_agent', 'Gemini']
    assert text == 'hello\n'
    assert alive is True


def test_tmux_pane_service_describes_pane_with_user_options() -> None:
    def tmux_run(args, **kwargs):
        if args == ['display-message', '-p', '-t', '%3', '#{pane_id}\t#{pane_title}\t#{pane_dead}\t#{@ccb_agent}\t#{@ccb_project_id}']:
            return _cp(stdout='%3\tagent2\t0\tagent2\tproj-1\n')
        return _cp(returncode=1)

    service = TmuxPaneService(
        tmux_run_fn=tmux_run,
        looks_like_pane_id_fn=lambda value: value.startswith('%'),
        normalize_split_direction_fn=lambda direction: ('-h', 'right'),
        pane_exists_output_fn=lambda output: output.strip().startswith('%'),
        pane_id_by_title_marker_output_fn=lambda text, marker: None,
        pane_is_alive_fn=lambda output: output.strip() == '0',
        normalize_user_option_fn=lambda name: '@' + name.strip('@'),
        strip_ansi_fn=lambda text: text,
    )

    described = service.describe_pane('%3', user_options=('@ccb_agent', '@ccb_project_id'))

    assert described == {
        'pane_id': '%3',
        'pane_title': 'agent2',
        'pane_dead': '0',
        '@ccb_agent': 'agent2',
        '@ccb_project_id': 'proj-1',
    }


def test_tmux_pane_service_finds_unique_pane_by_user_options() -> None:
    def tmux_run(args, **kwargs):
        if args == ['list-panes', '-a', '-F', '#{pane_id}\t#{@ccb_agent}\t#{@ccb_project_id}']:
            return _cp(stdout='%1\tagent1\tproj-1\n%2\tagent1\tproj-2\n')
        return _cp()

    service = TmuxPaneService(
        tmux_run_fn=tmux_run,
        looks_like_pane_id_fn=lambda value: value.startswith('%'),
        normalize_split_direction_fn=lambda direction: ('-h', 'right'),
        pane_exists_output_fn=lambda output: output.strip().startswith('%'),
        pane_id_by_title_marker_output_fn=lambda text, marker: None,
        pane_is_alive_fn=lambda output: output.strip() == '0',
        normalize_user_option_fn=lambda name: '@' + name.strip('@'),
        strip_ansi_fn=lambda text: text,
    )

    assert service.find_pane_by_user_options({'ccb_agent': 'agent1', 'ccb_project_id': 'proj-2'}) == '%2'


def test_tmux_pane_service_lists_matching_panes_by_user_options() -> None:
    def tmux_run(args, **kwargs):
        if args == ['list-panes', '-a', '-F', '#{pane_id}\t#{@ccb_project_id}']:
            return _cp(stdout='%1\tproj-1\n%2\tproj-2\n%3\tproj-2\n')
        return _cp()

    service = TmuxPaneService(
        tmux_run_fn=tmux_run,
        looks_like_pane_id_fn=lambda value: value.startswith('%'),
        normalize_split_direction_fn=lambda direction: ('-h', 'right'),
        pane_exists_output_fn=lambda output: output.strip().startswith('%'),
        pane_id_by_title_marker_output_fn=lambda text, marker: None,
        pane_is_alive_fn=lambda output: output.strip() == '0',
        normalize_user_option_fn=lambda name: '@' + name.strip('@'),
        strip_ansi_fn=lambda text: text,
    )

    assert service.list_panes_by_user_options({'ccb_project_id': 'proj-2'}) == ['%2', '%3']
