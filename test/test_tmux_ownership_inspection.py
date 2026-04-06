from __future__ import annotations

from types import SimpleNamespace

from provider_core.tmux_ownership import inspect_tmux_pane_ownership


def test_tmux_ownership_prefers_described_pane_match() -> None:
    class Backend:
        def describe_pane(self, pane_id: str, user_options: tuple[str, ...]):
            assert pane_id == "%12"
            assert user_options == ("@ccb_agent", "@ccb_project_id")
            return {
                "pane_title": "agent1",
                "@ccb_agent": "agent1",
                "@ccb_project_id": "proj_1",
            }

    session = SimpleNamespace(data={"agent_name": "agent1", "ccb_project_id": "proj_1"})

    ownership = inspect_tmux_pane_ownership(session, Backend(), "%12")

    assert ownership.is_owned is True
    assert ownership.pane_title == "agent1"
    assert ownership.actual_options == (
        ("@ccb_agent", "agent1"),
        ("@ccb_project_id", "proj_1"),
    )


def test_tmux_ownership_reports_foreign_when_listed_match_missing() -> None:
    class Backend:
        def list_panes_by_user_options(self, user_options: dict[str, str]):
            assert user_options == {"@ccb_agent": "agent1"}
            return ("%2", "%3")

    session = SimpleNamespace(data={"agent_name": "agent1"})

    ownership = inspect_tmux_pane_ownership(session, Backend(), "%9")

    assert ownership.is_owned is False
    assert ownership.state == "foreign"
    assert ownership.reason == "ownership-mismatch"
